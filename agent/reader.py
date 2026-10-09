# agent/reader.py
import requests
import os
import re

def download_pdf(pdf_url, paper_title):
    safe_title = "".join(c for c in paper_title if c.isalnum() or c in " -_")[:50]
    filename = f"outputs/{safe_title}.pdf"
    os.makedirs("outputs", exist_ok=True)
    if os.path.exists(filename):
        print(f"Already downloaded: {safe_title[:30]}")
        return filename
    try:
        print(f"Downloading: {safe_title[:40]}...")
        response = requests.get(pdf_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        with open(filename, "wb") as f:
            f.write(response.content)
        print("Downloaded successfully")
        return filename
    except Exception as e:
        print(f"Download failed: {e}")
        return None


def extract_text_from_pdf(pdf_path, max_pages=12):
    try:
        import fitz
        doc = fitz.open(pdf_path)
        text = ""
        for page_num in range(min(max_pages, len(doc))):
            text += doc[page_num].get_text()
        doc.close()
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 20]
        text = ' '.join(lines)
        words = text.split()[:5000]
        return ' '.join(words)
    except Exception as e:
        print(f"PDF reading failed: {e}")
        return None


def get_paper_text(paper):
    title = paper.get("title", "Unknown")
    pdf_url = paper.get("pdf_url")
    abstract = paper.get("abstract", "")
    authors = paper.get("authors", [])
    year = paper.get("year", "")
    venue = paper.get("venue", "")

    print(f"Processing: {title[:50]}...")

    if pdf_url:
        pdf_path = download_pdf(pdf_url, title)
        if pdf_path:
            text = extract_text_from_pdf(pdf_path)
            if text and len(text) > 200:
                return text

    # Fall back to abstract with metadata
    print("Using abstract only (no PDF available)")
    meta = f"Title: {title}\n"
    if authors:
        meta += f"Authors: {', '.join(authors)}\n"
    if year:
        meta += f"Year: {year}\n"
    if venue:
        meta += f"Venue: {venue}\n"
    meta += f"\nAbstract: {abstract}"
    return meta