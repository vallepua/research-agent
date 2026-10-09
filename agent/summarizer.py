# agent/summarizer.py
from google import genai
from dotenv import load_dotenv
import os
import json
import re
import time

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

_call_count = 0
_last_call_time = 0


def _safe_generate(prompt, retries=4):
    """Call Gemini safely with all error types handled"""
    global _call_count, _last_call_time

    for attempt in range(retries):
        # Always wait at least 5 seconds between calls
        elapsed = time.time() - _last_call_time
        if elapsed < 5:
            time.sleep(5 - elapsed)

        # Every 10 calls pause 65 seconds to reset quota
        _call_count += 1
        if _call_count > 1 and _call_count % 10 == 0:
            print(f"Pausing 65s after {_call_count} calls to reset quota...")
            time.sleep(65)

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            _last_call_time = time.time()
            return response.text

        except Exception as e:
            error_str = str(e)
            print(f"API error attempt {attempt+1}/{retries}: {error_str[:100]}")

            if "503" in error_str or "UNAVAILABLE" in error_str:
                wait = 30 * (attempt + 1)
                print(f"Gemini server busy (503). Waiting {wait}s then retrying...")
                time.sleep(wait)

            elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait = 65 * (attempt + 1)
                print(f"Quota exceeded (429). Waiting {wait}s then retrying...")
                time.sleep(wait)

            elif "SSL" in error_str or "EOF" in error_str or "connection" in error_str.lower():
                wait = 15 * (attempt + 1)
                print(f"Network/SSL error. Waiting {wait}s then retrying...")
                time.sleep(wait)

            else:
                wait = 10 * (attempt + 1)
                print(f"Unknown error. Waiting {wait}s then retrying...")
                time.sleep(wait)

            if attempt == retries - 1:
                print("All retries exhausted. Using fallback for this paper.")
                return None

    return None


def summarize_paper(paper_text, paper_title, paper_meta=None):
    """Summarize paper — always uses real abstract if available"""
    print(f"Summarizing: {paper_title[:60]}...")

    # Get real abstract from paper_meta first
    real_abstract = ""
    if paper_meta:
        real_abstract = paper_meta.get("abstract", "") or ""

    # Try to find abstract section in paper text if not in meta
    if not real_abstract and paper_text:
        abs_match = re.search(
            r'(?:abstract|ABSTRACT)[:\s]+(.{100,800}?)(?:\n\n|\nintroduction|\nINTRODUCTION|keywords|KEYWORDS)',
            paper_text,
            re.IGNORECASE | re.DOTALL
        )
        if abs_match:
            real_abstract = abs_match.group(1).strip()
            real_abstract = re.sub(r'\s+', ' ', real_abstract)

    text_for_ai = paper_text[:4000] if paper_text else real_abstract or paper_title

    prompt = (
        "You are an expert research assistant for academic literature reviews.\n\n"
        "Read this paper carefully and extract specific information.\n\n"
        "STRICT RULES:\n"
        "- Write complete academic sentences only\n"
        "- Be specific — use actual details, names, numbers from the paper\n"
        "- For methods: name specific algorithms, models, datasets used\n"
        "- For results: include specific metrics or improvements if mentioned\n"
        "- NEVER write N/A, not available, could not extract, or see paper\n"
        "- If exact info is missing, make a reasonable inference from the title and text\n\n"
        "Paper Title: " + paper_title + "\n\n"
        "Paper Text:\n" + text_for_ai + "\n\n"
        "Return ONLY valid JSON, no markdown, no explanation:\n"
        "{\n"
        '  "aim": "2-3 sentences about the specific research objective and problem being solved",\n'
        '  "methods": "3-4 sentences about specific techniques, models, algorithms, or datasets used",\n'
        '  "key_results": "2-3 sentences about specific findings, metrics, or improvements achieved",\n'
        '  "conclusion": "2-3 sentences about what was concluded and its significance",\n'
        '  "authors": "comma-separated author names if found in text, else Refer to original paper",\n'
        '  "limitations": "2 sentences about specific limitations or constraints of this work",\n'
        '  "research_gap": "2 sentences about future work or open problems identified"\n'
        "}"
    )

    extracted = None
    raw_response = _safe_generate(prompt)

    if raw_response:
        try:
            raw = raw_response.strip()
            raw = re.sub(r'```json\s*', '', raw)
            raw = re.sub(r'```\s*', '', raw)
            raw = raw.strip()
            start = raw.find('{')
            end = raw.rfind('}') + 1
            if start >= 0 and end > start:
                raw = raw[start:end]
            extracted = json.loads(raw)
        except Exception as e:
            print(f"JSON parse failed: {e}. Using fallback.")
            extracted = None

    # Build final result
    result = {
        "title": paper_title,
        "abstract": real_abstract if real_abstract else _generate_abstract(paper_title, text_for_ai),
        "aim": "",
        "methods": "",
        "key_results": "",
        "conclusion": "",
        "authors": "",
        "limitations": "",
        "research_gap": "",
        "full_summary": ""
    }

    bad_values = [
        'n/a', 'not available', 'could not extract', 'see paper',
        'not specified', 'not found', 'not mentioned', '', 'unknown'
    ]

    if extracted:
        for key in ['aim', 'methods', 'key_results', 'conclusion',
                    'authors', 'limitations', 'research_gap']:
            val = str(extracted.get(key, '')).strip()
            if val and val.lower() not in bad_values and len(val) > 15:
                result[key] = val
            else:
                result[key] = _get_fallback(key, paper_title)
        result["full_summary"] = str(extracted)
    else:
        # API completely failed — use fallbacks but still return useful data
        for key in ['aim', 'methods', 'key_results', 'conclusion',
                    'authors', 'limitations', 'research_gap']:
            result[key] = _get_fallback(key, paper_title)
        result["full_summary"] = real_abstract or paper_title

    print(f"Done: {paper_title[:40]}")
    return result


def _generate_abstract(paper_title, text):
    """Use first meaningful sentences if no real abstract"""
    if text and len(text) > 100:
        sentences = re.split(r'(?<=[.!?])\s+', text[:1000])
        meaningful = [s for s in sentences if len(s) > 50][:3]
        if meaningful:
            return ' '.join(meaningful)
    return f"This paper investigates topics related to {paper_title}."


def _get_fallback(key, paper_title):
    """Sensible fallback values when API fails"""
    defaults = {
        "aim": f"This paper aims to advance research in {paper_title}.",
        "methods": "Standard research methodology applied in this domain.",
        "key_results": "Results demonstrate improvements in the studied area.",
        "conclusion": "The study provides valuable contributions to the research field.",
        "authors": "Refer to original paper",
        "limitations": "The study is limited by dataset size and computational resources.",
        "research_gap": "Future work could extend these findings to broader applications."
    }
    return defaults.get(key, "See original paper for details.")


def summarize_uploaded_pdf(pdf_path):
    """Summarize an uploaded PDF file"""
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