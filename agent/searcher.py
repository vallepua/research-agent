# agent/searcher.py
import requests
import time
import urllib.parse
import xml.etree.ElementTree as ET
import re

def search_papers(topic, max_papers=10, year_from=2020):
    """Search 5 sources in order until enough papers found"""
    print(f"Searching for: {topic}")
    all_papers = []

    # Source 1: Semantic Scholar
    print("Trying Semantic Scholar...")
    papers = _search_semantic_scholar(topic, max_papers)
    if papers:
        all_papers.extend(papers)
        print(f"Semantic Scholar: {len(papers)} papers")
        if len(all_papers) >= max_papers:
            return all_papers[:max_papers]

    # Source 2: arXiv
    print("Trying arXiv...")
    papers = _search_arxiv(topic, max_papers - len(all_papers))
    if papers:
        # Avoid duplicates by title
        existing = {p['title'].lower()[:40] for p in all_papers}
        new = [p for p in papers if p['title'].lower()[:40] not in existing]
        all_papers.extend(new)
        print(f"arXiv: {len(new)} new papers")
        if len(all_papers) >= max_papers:
            return all_papers[:max_papers]

    # Source 3: CrossRef
    print("Trying CrossRef...")
    papers = _search_crossref(topic, max_papers - len(all_papers))
    if papers:
        existing = {p['title'].lower()[:40] for p in all_papers}
        new = [p for p in papers if p['title'].lower()[:40] not in existing]
        all_papers.extend(new)
        print(f"CrossRef: {len(new)} new papers")
        if len(all_papers) >= max_papers:
            return all_papers[:max_papers]

    # Source 4: Europe PMC (biomedical + general science)
    print("Trying Europe PMC...")
    papers = _search_europe_pmc(topic, max_papers - len(all_papers))
    if papers:
        existing = {p['title'].lower()[:40] for p in all_papers}
        new = [p for p in papers if p['title'].lower()[:40] not in existing]
        all_papers.extend(new)
        print(f"Europe PMC: {len(new)} new papers")
        if len(all_papers) >= max_papers:
            return all_papers[:max_papers]

    # Source 5: CORE API (open access)
    print("Trying CORE...")
    papers = _search_core(topic, max_papers - len(all_papers))
    if papers:
        existing = {p['title'].lower()[:40] for p in all_papers}
        new = [p for p in papers if p['title'].lower()[:40] not in existing]
        all_papers.extend(new)
        print(f"CORE: {len(new)} new papers")

    if not all_papers:
        print("No papers found from any source")
    else:
        print(f"Total: {len(all_papers)} papers from all sources")

    return all_papers[:max_papers]


def _search_semantic_scholar(topic, max_papers):
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": topic,
        "limit": min(max_papers, 10),
        "fields": "title,abstract,authors,year,venue,openAccessPdf,externalIds",
    }
    for attempt in range(2):
        try:
            time.sleep(2)
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 429:
                print("Semantic Scholar rate limited, skipping...")
                return []
            if response.status_code != 200:
                return []
            data = response.json()
            papers = []
            for paper in data.get("data", []):
                if not paper.get("title"):
                    continue
                pdf_url = None
                if paper.get("openAccessPdf"):
                    pdf_url = paper["openAccessPdf"].get("url")
                papers.append({
                    "title": paper.get("title", "Unknown"),
                    "abstract": paper.get("abstract") or "",
                    "authors": [a["name"] for a in paper.get("authors", [])],
                    "year": str(paper.get("year") or "Unknown"),
                    "venue": paper.get("venue") or "Unknown",
                    "pdf_url": pdf_url,
                    "source": "Semantic Scholar"
                })
            return papers
        except Exception as e:
            print(f"Semantic Scholar attempt {attempt+1} failed: {e}")
            time.sleep(3)
    return []


def _search_arxiv(topic, max_papers):
    if max_papers <= 0:
        return []
    try:
        query = urllib.parse.quote(topic)
        url = f"http://export.arxiv.org/api/query?search_query=all:{query}&start=0&max_results={max_papers}&sortBy=relevance&sortOrder=descending"
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            return []
        root = ET.fromstring(response.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        papers = []
        for entry in root.findall('atom:entry', ns):
            title_el = entry.find('atom:title', ns)
            summary_el = entry.find('atom:summary', ns)
            if title_el is None:
                continue
            pdf_url = None
            for link in entry.findall('atom:link', ns):
                if link.get('type') == 'application/pdf':
                    pdf_url = link.get('href')
                    break
            authors = []
            for author in entry.findall('atom:author', ns):
                name = author.find('atom:name', ns)
                if name is not None:
                    authors.append(name.text)
            published = entry.find('atom:published', ns)
            year = published.text[:4] if published is not None else "Unknown"
            abstract = summary_el.text.strip() if summary_el is not None else ""
            # Clean abstract
            abstract = re.sub(r'\s+', ' ', abstract).strip()
            papers.append({
                "title": title_el.text.strip().replace('\n', ' '),
                "abstract": abstract,
                "authors": authors[:5],
                "year": year,
                "venue": "arXiv",
                "pdf_url": pdf_url,
                "source": "arXiv"
            })
        return papers
    except Exception as e:
        print(f"arXiv search failed: {e}")
        return []


def _search_crossref(topic, max_papers):
    if max_papers <= 0:
        return []
    try:
        url = "https://api.crossref.org/works"
        params = {
            "query": topic,
            "rows": min(max_papers, 10),
            "select": "title,abstract,author,published,URL,container-title",
            "sort": "relevance"
        }
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            return []
        data = response.json()
        papers = []
        for item in data.get("message", {}).get("items", []):
            titles = item.get("title", [])
            if not titles:
                continue
            authors = []
            for author in item.get("author", [])[:5]:
                name = f"{author.get('given', '')} {author.get('family', '')}".strip()
                if name:
                    authors.append(name)
            year = "Unknown"
            published = item.get("published", {})
            date_parts = published.get("date-parts", [[]])
            if date_parts and date_parts[0]:
                year = str(date_parts[0][0])
            abstract = item.get("abstract", "")
            if abstract:
                abstract = re.sub('<[^<]+?>', '', abstract).strip()
            venue = ""
            ct = item.get("container-title", [])
            if ct:
                venue = ct[0]
            papers.append({
                "title": titles[0],
                "abstract": abstract,
                "authors": authors,
                "year": year,
                "venue": venue or "Journal Article",
                "pdf_url": item.get("URL"),
                "source": "CrossRef"
            })
        return papers
    except Exception as e:
        print(f"CrossRef search failed: {e}")
        return []


def _search_europe_pmc(topic, max_papers):
    if max_papers <= 0:
        return []
    try:
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": topic,
            "format": "json",
            "pageSize": min(max_papers, 10),
            "resultType": "core",
            "sort": "RELEVANCE"
        }
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            return []
        data = response.json()
        papers = []
        for item in data.get("resultList", {}).get("result", []):
            title = item.get("title", "").strip()
            if not title:
                continue
            abstract = item.get("abstractText", "") or ""
            abstract = re.sub(r'\s+', ' ', abstract).strip()
            authors_list = []
            author_list = item.get("authorList", {}).get("author", [])
            for a in author_list[:5]:
                name = a.get("fullName", "")
                if name:
                    authors_list.append(name)
            year = str(item.get("pubYear", "Unknown"))
            venue = item.get("journalTitle", "") or item.get("bookOrReportDetails", {}).get("publisher", "") or "Unknown"
            pdf_url = None
            if item.get("fullTextUrlList"):
                for url_item in item["fullTextUrlList"].get("fullTextUrl", []):
                    if url_item.get("documentStyle") == "pdf":
                        pdf_url = url_item.get("url")
                        break
            papers.append({
                "title": title,
                "abstract": abstract,
                "authors": authors_list,
                "year": year,
                "venue": venue,
                "pdf_url": pdf_url,
                "source": "Europe PMC"
            })
        return papers
    except Exception as e:
        print(f"Europe PMC search failed: {e}")
        return []


def _search_core(topic, max_papers):
    if max_papers <= 0:
        return []
    try:
        url = "https://api.core.ac.uk/v3/search/works"
        params = {
            "q": topic,
            "limit": min(max_papers, 10),
        }
        headers = {"Accept": "application/json"}
        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code != 200:
            return []
        data = response.json()
        papers = []
        for item in data.get("results", []):
            title = item.get("title", "").strip()
            if not title:
                continue
            abstract = item.get("abstract", "") or ""
            abstract = re.sub(r'\s+', ' ', abstract[:1000]).strip()
            authors_list = []
            for a in item.get("authors", [])[:5]:
                name = a.get("name", "")
                if name:
                    authors_list.append(name)
            year = str(item.get("yearPublished", "Unknown"))
            venue = ""
            journals = item.get("journals", [])
            if journals:
                venue = journals[0].get("title", "") or ""
            pdf_url = item.get("downloadUrl")
            papers.append({
                "title": title,
                "abstract": abstract,
                "authors": authors_list,
                "year": year,
                "venue": venue or "Open Access",
                "pdf_url": pdf_url,
                "source": "CORE"
            })
        return papers
    except Exception as e:
        print(f"CORE search failed: {e}")
        return []