# agent/writer.py
from google import genai
from dotenv import load_dotenv
import os
import time

load_dotenv()

def _get_api_key():
    try:
        import streamlit as st
        return st.secrets["GEMINI_API_KEY"]
    except:
        return os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=_get_api_key())


def write_literature_review(topic, summaries):
    print(f"Writing literature review for: {topic}")

    summaries_text = ""
    for i, s in enumerate(summaries, 1):
        summaries_text += f"\nPaper {i}: {s.get('title', '')[:80]}\n"
        summaries_text += f"- Aim: {s.get('aim', '')[:200]}\n"
        summaries_text += f"- Methods: {s.get('methods', '')[:200]}\n"
        summaries_text += f"- Results: {s.get('key_results', '')[:150]}\n"
        summaries_text += f"- Gap: {s.get('research_gap', '')[:150]}\n"

    prompt = (
        "You are an expert academic writer. Write a formal literature review.\n\n"
        "Topic: " + topic + "\n\n"
        "Papers:\n" + summaries_text + "\n\n"
        "Write with these sections:\n"
        "# Literature Review: " + topic + "\n\n"
        "## 1. Introduction\n"
        "## 2. Main Approaches and Methods\n"
        "## 3. Key Findings\n"
        "## 4. Research Gaps and Challenges\n"
        "## 5. Conclusion and Future Directions\n"
        "## References\n\n"
        "Use formal academic English. Minimum 600 words."
    )

    for attempt in range(4):
        try:
            wait_time = 10 * (attempt + 1) if attempt > 0 else 5
            time.sleep(wait_time)

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            review_text = response.text
            if review_text and len(review_text) > 200:
                print(f"Literature review generated ({len(review_text)} chars)")
                return review_text

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                time.sleep(70 * (attempt + 1))
            elif "503" in error_str or "UNAVAILABLE" in error_str:
                time.sleep(30 * (attempt + 1))
            elif "SSL" in error_str or "EOF" in error_str:
                time.sleep(15)
            else:
                time.sleep(10)

    return None


def save_review(topic, review_text):
    if not review_text:
        return None
    os.makedirs("outputs", exist_ok=True)
    safe = "".join(c for c in topic if c.isalnum() or c in " -_")[:40]
    filename = f"outputs/literature_review_{safe}.md"
    with open(filename, "w") as f:
        f.write(review_text)
    print(f"Saved: {filename}")
    return filename