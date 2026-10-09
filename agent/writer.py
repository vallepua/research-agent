# agent/writer.py
from google import genai
from dotenv import load_dotenv
import os
import time
import re

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def write_literature_review(topic, summaries):
    print(f"Writing literature review for: {topic}")

    # Build a concise summary to avoid token limits
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
        "Use formal academic English. Be specific. Minimum 600 words."
    )

    for attempt in range(4):
        try:
            # Wait longer between attempts
            wait_time = 10 * (attempt + 1)
            if attempt > 0:
                print(f"Retrying literature review (attempt {attempt+1})... waiting {wait_time}s")
                time.sleep(wait_time)
            else:
                time.sleep(5)

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
                wait = 70 * (attempt + 1)
                print(f"Quota limit. Waiting {wait}s...")
                time.sleep(wait)
            elif "SSL" in error_str or "EOF" in error_str:
                print(f"SSL/Network error on attempt {attempt+1}. Retrying...")
                time.sleep(15)
            else:
                print(f"Writing error: {e}")
                time.sleep(10)

    print("All attempts failed for literature review")
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