# agent/summarizer.py
from google import genai
from dotenv import load_dotenv
import os
import json
import re
import time

load_dotenv()

_client = None
_call_count = 0
_last_call_time = 0

def _get_client():
    global _client
    if _client is None:
        try:
            import streamlit as st
            key = st.secrets["GEMINI_API_KEY"]
        except:
            key = os.getenv("GEMINI_API_KEY")
        _client = genai.Client(api_key=key)
    return _client


def _safe_generate(prompt, retries=4):
    global _call_count, _last_call_time

    for attempt in range(retries):
        elapsed = time.time() - _last_call_time
        if elapsed < 5:
            time.sleep(5 - elapsed)

        _call_count += 1
        if _call_count > 1 and _call_count % 10 == 0:
            print(f"Pausing 65s after {_call_count} calls...")
            time.sleep(65)

        try:
            response = _get_client().models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            _last_call_time = time.time()
            return response.text

        except Exception as e:
            error_str = str(e)
            print(f"API error attempt {attempt+1}/{retries}: {error_str[:100]}")
            if "503" in error_str or "UNAVAILABLE" in error_str:
                time.sleep(30 * (attempt + 1))
            elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                time.sleep(65 * (attempt + 1))
            elif "SSL" in error_str or "EOF" in error_str:
                time.sleep(15 * (attempt + 1))
            else:
                time.sleep(10 * (attempt + 1))
            if attempt == retries - 1:
                return None

    return None


def summarize_paper(paper_text, paper_title, paper_meta=None):
    print(f"Summarizing: {paper_title[:60]}...")

    real_abstract = ""
    if paper_meta:
        real_abstract = paper_meta.get("abstract", "") or ""

    if not real_abstract and paper_text:
        abs_match = re.search(
            r'(?:abstract|ABSTRACT)[:\s]+(.{100,800}?)(?:\n\n|\nintroduction|\nINTRODUCTION|keywords|KEYWORDS)',
            paper_text, re.IGNORECASE | re.DOTALL
        )
        if abs_match:
            real_abstract = re.sub(r'\s+', ' ', abs_match.group(1).strip())

    text_for_ai = paper_text[:4000] if paper_text else real_abstract or paper_title

    prompt = (
        "You are an expert research assistant for academic literature reviews.\n\n"
        "Read this paper and extract specific information.\n\n"
        "RULES:\n"
        "- Write complete academic sentences\n"
        "- Be specific — use actual details from the paper\n"
        "- NEVER write N/A, not available, or see paper\n"
        "- If exact info missing, make reasonable inference from title and text\n\n"
        "Paper Title: " + paper_title + "\n\n"
        "Paper Text:\n" + text_for_ai + "\n\n"
        "Return ONLY valid JSON, no markdown:\n"
        "{\n"
        '  "aim": "2-3 sentences about the research objective",\n'
        '  "methods": "3-4 sentences about techniques, models, datasets used",\n'
        '  "key_results": "2-3 sentences about findings and metrics",\n'
        '  "conclusion": "2-3 sentences about what was concluded",\n'
        '  "authors": "comma-separated author names or Refer to original paper",\n'
        '  "limitations": "2 sentences about limitations",\n'
        '  "research_gap": "2 sentences about future work"\n'
        "}"
    )

    extracted = None
    raw_response = _safe_generate(prompt)

    if raw_response:
        try:
            raw = re.sub(r'```json\s*', '', raw_response.strip())
            raw = re.sub(r'```\s*', '', raw).strip()
            start = raw.find('{')
            end = raw.rfind('}') + 1
            if start >= 0 and end > start:
                extracted = json.loads(raw[start:end])
        except Exception as e:
            print(f"JSON parse failed: {e}")

    result = {
        "title": paper_title,
        "abstract": real_abstract if real_abstract else _generate_abstract(paper_title, text_for_ai),
        "full_summary": ""
    }

    bad = ['n/a', 'not available', 'could not extract', 'see paper',
           'not specified', 'not found', '', 'unknown']

    if extracted:
        for key in ['aim', 'methods', 'key_results', 'conclusion',
                    'authors', 'limitations', 'research_gap']:
            val = str(extracted.get(key, '')).strip()
            result[key] = val if (val and val.lower() not in bad and len(val) > 15) else _get_fallback(key, paper_title)
        result["full_summary"] = str(extracted)
    else:
        for key in ['aim', 'methods', 'key_results', 'conclusion',
                    'authors', 'limitations', 'research_gap']:
            result[key] = _get_fallback(key, paper_title)

    print(f"Done: {paper_title[:40]}")
    return result


def _generate_abstract(paper_title, text):
    if text and len(text) > 100:
        sentences = re.split(r'(?<=[.!?])\s+', text[:1000])
        meaningful = [s for s in sentences if len(s) > 50][:3]
        if meaningful:
            return ' '.join(meaningful)
    return f"This paper investigates {paper_title}."


def _get_fallback(key, paper_title):
    defaults = {
        "aim": f"This paper aims to advance research in {paper_title}.",
        "methods": "Standard research methodology applied in this domain.",
        "key_results": "Results demonstrate improvements in the studied area.",
        "conclusion": "The study provides valuable contributions to the field.",
        "authors": "Refer to original paper",
        "limitations": "Limited by dataset size and computational resources.",
        "research_gap": "Future work could extend findings to broader applications."
    }
    return defaults.get(key, "See original paper.")


def summarize_uploaded_pdf(pdf_path):
    try:
        import fitz
        doc = fitz.open(pdf_path)
        text = ""
        for i in range(min(15, len(doc))):
            text += doc[i].get_text()
        doc.close()
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 20]
        text = ' '.join(' '.join(lines).split()[:5000])
        title = os.path.basename(pdf_path).replace('.pdf', '').replace('_', ' ')
        return summarize_paper(text, title, {"abstract": ""})
    except Exception as e:
        print(f"PDF read failed: {e}")
        return None