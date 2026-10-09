# app.py
import streamlit as st
from google import genai
from dotenv import load_dotenv
import os
import sys
import tempfile
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent.searcher import search_papers
from agent.reader import get_paper_text
from agent.summarizer import summarize_paper, summarize_uploaded_pdf
from agent.writer import write_literature_review, save_review

# Load API key - works both locally and on Streamlit Cloud
load_dotenv()
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    api_key = os.getenv("GEMINI_API_KEY")

os.environ["GEMINI_API_KEY"] = api_key or ""

st.set_page_config(
    page_title="Research Paper Assistant",
    page_icon="🔬",
    layout="wide"
)

st.title("🔬 Research Paper Assistant Agent")
st.markdown("*Search any topic → finds papers from 5 sources, builds structured literature review table*")
st.divider()

with st.sidebar:
    st.header("⚙️ Settings")
    num_papers = st.slider("Number of papers", 3, 15, 5)
    year_from = st.slider("Papers from year", 2015, 2026, 2020)
    st.divider()
    st.markdown("**Sources searched:**")
    st.markdown("• Semantic Scholar")
    st.markdown("• arXiv")
    st.markdown("• CrossRef")
    st.markdown("• Europe PMC")
    st.markdown("• CORE (Open Access)")
    st.divider()
    st.info("⏱️ Allow 1-2 min per paper for AI summarization.")

tab1, tab2 = st.tabs(["🔍 Search & Review", "📤 Upload Your Paper"])

with tab1:
    topic = st.text_input(
        "📝 Enter your research topic:",
        placeholder="e.g. Large language models for medical diagnosis"
    )
    run_button = st.button("🚀 Generate Literature Review", type="primary")

    if run_button and topic:
        st.divider()

        with st.status("🔍 Searching 5 sources for papers...", expanded=True) as status:
            papers = search_papers(topic, max_papers=num_papers, year_from=year_from)
            if not papers:
                st.error("No papers found. Try a broader topic.")
                st.stop()
            sources = {}
            for p in papers:
                src = p.get('source', 'Unknown')
                sources[src] = sources.get(src, 0) + 1
            source_str = " | ".join([f"{k}: {v}" for k, v in sources.items()])
            st.write(f"✅ Found {len(papers)} papers — {source_str}")
            status.update(label=f"✅ Found {len(papers)} papers", state="complete")

        with st.expander(f"📚 Papers Found ({len(papers)})", expanded=False):
            for i, p in enumerate(papers, 1):
                authors = ', '.join(p.get('authors', [])[:3])
                st.markdown(f"**{i}. {p['title']}** ({p.get('year','')}) — *{p.get('venue','?')}*")
                st.caption(f"Authors: {authors} | Source: {p.get('source','')} | PDF: {'✅' if p.get('pdf_url') else '❌ abstract only'}")
                st.divider()

        summaries = []
        progress = st.progress(0, text="Starting summarization...")
        status_box = st.empty()

        for i, paper in enumerate(papers):
            pct = i / len(papers)
            progress.progress(pct, text=f"📄 {i+1}/{len(papers)}: {paper['title'][:50]}...")
            status_box.info(f"🤖 Summarizing paper {i+1}/{len(papers)}: {paper['title'][:60]}...")

            text = get_paper_text(paper)
            summary = summarize_paper(
                text,
                paper['title'],
                paper_meta={
                    "abstract": paper.get("abstract", ""),
                    "authors": paper.get("authors", []),
                    "year": paper.get("year", ""),
                    "venue": paper.get("venue", "")
                }
            )
            summary["venue"] = paper.get("venue", "Unknown")
            summary["year"] = paper.get("year", "Unknown")
            summary["paper_authors"] = ', '.join(paper.get("authors", [])[:5]) or summary.get("authors", "")
            if paper.get("abstract") and len(paper.get("abstract", "")) > 30:
                summary["abstract"] = paper["abstract"]
            summaries.append(summary)

        progress.progress(1.0, text="✅ All papers summarized!")
        status_box.empty()

        st.divider()
        st.markdown("## 📊 Literature Review Table")
        st.caption("Structured summary — download as Excel for your literature survey")

        rows = []
        for s in summaries:
            rows.append({
                "Paper Title": s.get("title", ""),
                "Published Venue": s.get("venue", "Unknown"),
                "Year": s.get("year", ""),
                "Authors": s.get("paper_authors", s.get("authors", "")),
                "Abstract": s.get("abstract", ""),
                "Aim of the Paper": s.get("aim", ""),
                "Methods Used": s.get("methods", ""),
                "Key Results": s.get("key_results", ""),
                "Conclusion": s.get("conclusion", ""),
                "Limitations / Open Challenges": s.get("limitations", ""),
                "Identified Research Gap": s.get("research_gap", ""),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, height=450)

        col1, col2 = st.columns(2)
        with col1:
            excel_path = f"/tmp/lit_{topic[:20].replace(' ','_')}.xlsx"
            df.to_excel(excel_path, index=False, engine='openpyxl')
            with open(excel_path, "rb") as f:
                st.download_button(
                    "📥 Download Excel (.xlsx)",
                    data=f.read(),
                    file_name=f"literature_review_{topic[:30]}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        with col2:
            st.download_button(
                "📥 Download CSV",
                data=df.to_csv(index=False),
                file_name=f"literature_review_{topic[:30]}.csv",
                mime="text/csv"
            )

        st.divider()
        st.markdown("## ✍️ Full Literature Review")
        with st.status("Writing literature review...", expanded=True) as status:
            review = write_literature_review(topic, summaries)
            if review:
                save_review(topic, review)
                status.update(label="✅ Literature review complete!", state="complete")
                st.markdown(review)
                st.download_button(
                    "📥 Download Literature Review (.md)",
                    data=review,
                    file_name=f"literature_review_{topic[:30]}.md",
                    mime="text/markdown"
                )
            else:
                status.update(label="⚠️ Could not generate review text", state="error")
                st.warning("API limit reached. Your table above has all the data. Try again in a few minutes.")

    elif run_button and not topic:
        st.warning("⚠️ Please enter a research topic first!")


with tab2:
    st.markdown("## 📤 Upload Your Own Paper")
    st.markdown("Upload any PDF — get an instant structured summary in the same table format.")

    uploaded_file = st.file_uploader("Choose a PDF", type=['pdf'])

    if uploaded_file:
        st.success(f"✅ Uploaded: {uploaded_file.name}")

        if st.button("🤖 Summarize This Paper", type="primary"):
            with st.spinner("Reading and summarizing..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                summary = summarize_uploaded_pdf(tmp_path)
                os.unlink(tmp_path)

            if summary:
                st.divider()
                st.markdown(f"### 📋 {summary['title']}")

                row = [{
                    "Paper Title": summary.get("title", ""),
                    "Published Venue": "Uploaded by user",
                    "Year": "—",
                    "Authors": summary.get("authors", ""),
                    "Abstract": summary.get("abstract", ""),
                    "Aim of the Paper": summary.get("aim", ""),
                    "Methods Used": summary.get("methods", ""),
                    "Key Results": summary.get("key_results", ""),
                    "Conclusion": summary.get("conclusion", ""),
                    "Limitations / Open Challenges": summary.get("limitations", ""),
                    "Identified Research Gap": summary.get("research_gap", ""),
                }]
                df2 = pd.DataFrame(row)
                st.dataframe(df2, use_container_width=True)

                excel_path2 = f"/tmp/summary_{uploaded_file.name}.xlsx"
                df2.to_excel(excel_path2, index=False, engine='openpyxl')
                with open(excel_path2, "rb") as f:
                    st.download_button(
                        "📥 Download as Excel",
                        data=f.read(),
                        file_name=f"summary_{uploaded_file.name}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                with st.expander("📖 Full Details", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        for field, label in [("aim", "🎯 Aim"), ("methods", "🔧 Methods"),
                                              ("key_results", "📈 Key Results"), ("conclusion", "✅ Conclusion")]:
                            st.markdown(f"**{label}**")
                            st.write(summary.get(field, ""))
                    with col2:
                        for field, label in [("authors", "👥 Authors"), ("limitations", "⚠️ Limitations"),
                                              ("research_gap", "🔭 Research Gap")]:
                            st.markdown(f"**{label}**")
                            st.write(summary.get(field, ""))
            else:
                st.error("Could not summarize. Try another PDF.")