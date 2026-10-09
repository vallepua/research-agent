# app.py - Research Paper Assistant Agent
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

load_dotenv()

st.set_page_config(
    page_title="Research Paper Assistant",
    page_icon="🔬",
    layout="wide"
)

st.title("🔬 Research Paper Assistant Agent")
st.markdown("*Search any topic → Agent finds papers, reads them, builds a full literature review table*")
st.divider()

with st.sidebar:
    st.header("⚙️ Settings")
    num_papers = st.slider("Number of papers", 3, 20, 5)
    year_from = st.slider("Papers from year", 2015, 2026, 2020)
    st.divider()
    st.markdown("**Pipeline:**")
    st.markdown("1. 🔍 Semantic Scholar → arXiv → CrossRef")
    st.markdown("2. 📥 Downloads & reads PDFs")
    st.markdown("3. 🤖 Gemini summarizes each paper")
    st.markdown("4. 📊 Structured Excel/CSV table")
    st.markdown("5. ✍️ Full literature review")
    st.markdown("6. 📤 Upload your own PDF")
    st.divider()
    st.info("Note: Processing takes 1-2 min per paper due to API rate limits.")

tab1, tab2 = st.tabs(["🔍 Search & Review", "📤 Upload Your Paper"])

# ── TAB 1 ──────────────────────────────────────────────────
with tab1:
    topic = st.text_input(
        "📝 Enter your research topic:",
        placeholder="e.g. Large language models for medical diagnosis"
    )
    run_button = st.button("🚀 Generate Literature Review", type="primary")

    if run_button and topic:
        st.divider()

        # STEP 1 — Search
        with st.status("🔍 Searching papers...", expanded=True) as status:
            papers = search_papers(topic, max_papers=num_papers, year_from=year_from)
            if not papers:
                st.error("No papers found. Try a broader topic.")
                st.stop()
            st.write(f"✅ Found {len(papers)} papers")
            status.update(label=f"✅ Found {len(papers)} papers", state="complete")

        # Show found papers
        with st.expander(f"📚 Papers Found ({len(papers)})", expanded=False):
            for i, p in enumerate(papers, 1):
                authors = ', '.join(p.get('authors', [])[:3])
                st.markdown(f"**{i}. {p['title']}** ({p.get('year','')}) — *{p.get('venue','Unknown venue')}*")
                st.markdown(f"Authors: {authors}")
                st.markdown(f"Source: {p.get('source','')} | PDF: {'✅' if p.get('pdf_url') else '❌'}")
                st.divider()

        # STEP 2 — Read + Summarize
        summaries = []
        progress = st.progress(0, text="Starting...")

        for i, paper in enumerate(papers):
            pct = i / len(papers)
            progress.progress(pct, text=f"📄 Paper {i+1}/{len(papers)}: {paper['title'][:45]}...")
            text = get_paper_text(paper)
            summary = summarize_paper(
                text,
                paper['title'],
                paper_meta={
                    "authors": paper.get("authors", []),
                    "year": paper.get("year", ""),
                    "venue": paper.get("venue", "")
                }
            )
            # Add venue and year from search results
            summary["venue"] = paper.get("venue", "Unknown")
            summary["year"] = paper.get("year", "Unknown")
            summary["paper_authors"] = ', '.join(paper.get("authors", [])[:5]) or summary.get("authors", "")
            summaries.append(summary)

        progress.progress(1.0, text="✅ All papers processed!")

        # STEP 3 — Build Table
        st.divider()
        st.markdown("## 📊 Literature Review Table")
        st.markdown("*Structured summary of all papers — download as Excel for your literature survey*")

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

        st.dataframe(
            df,
            use_container_width=True,
            height=450,
            column_config={
                "Paper Title": st.column_config.TextColumn(width="large"),
                "Published Venue": st.column_config.TextColumn(width="medium"),
                "Year": st.column_config.TextColumn(width="small"),
                "Authors": st.column_config.TextColumn(width="medium"),
                "Abstract": st.column_config.TextColumn(width="large"),
                "Aim of the Paper": st.column_config.TextColumn(width="large"),
                "Methods Used": st.column_config.TextColumn(width="large"),
                "Key Results": st.column_config.TextColumn(width="large"),
                "Conclusion": st.column_config.TextColumn(width="large"),
                "Limitations / Open Challenges": st.column_config.TextColumn(width="large"),
                "Identified Research Gap": st.column_config.TextColumn(width="large"),
            }
        )

        # Download as Excel
        excel_path = f"/tmp/literature_table_{topic[:20].replace(' ','_')}.xlsx"
        df.to_excel(excel_path, index=False, engine='openpyxl')
        with open(excel_path, "rb") as f:
            st.download_button(
                label="📥 Download as Excel (.xlsx)",
                data=f.read(),
                file_name=f"literature_review_{topic[:30]}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        # Also CSV
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"literature_review_{topic[:30]}.csv",
            mime="text/csv"
        )

        # STEP 4 — Literature Review
        st.divider()
        st.markdown("## ✍️ Full Literature Review")
        with st.status("Writing literature review...", expanded=True) as status:
            review = write_literature_review(topic, summaries)
            if not review:
                st.error("Failed to generate review. Download the table above — it has all the data.")
                st.stop()
            save_review(topic, review)
            status.update(label="✅ Literature review complete!", state="complete")

        st.markdown(review)

        st.download_button(
            label="📥 Download Literature Review (.md)",
            data=review,
            file_name=f"literature_review_{topic[:30]}.md",
            mime="text/markdown"
        )

    elif run_button and not topic:
        st.warning("⚠️ Please enter a research topic first!")


# ── TAB 2 ──────────────────────────────────────────────────
with tab2:
    st.markdown("## 📤 Upload Your Own Paper")
    st.markdown("Upload any research PDF — get an instant structured summary in the same table format.")

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
                st.markdown(f"### 📋 Summary: {summary['title']}")

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

                # Download Excel
                excel_path2 = f"/tmp/summary_{uploaded_file.name}.xlsx"
                df2.to_excel(excel_path2, index=False, engine='openpyxl')
                with open(excel_path2, "rb") as f:
                    st.download_button(
                        label="📥 Download Summary as Excel",
                        data=f.read(),
                        file_name=f"summary_{uploaded_file.name}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                # Detailed view
                with st.expander("📖 Full Detailed Summary", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**🎯 Aim**")
                        st.write(summary.get("aim", ""))
                        st.markdown("**🔧 Methods**")
                        st.write(summary.get("methods", ""))
                        st.markdown("**📈 Key Results**")
                        st.write(summary.get("key_results", ""))
                        st.markdown("**✅ Conclusion**")
                        st.write(summary.get("conclusion", ""))
                    with col2:
                        st.markdown("**👥 Authors**")
                        st.write(summary.get("authors", ""))
                        st.markdown("**⚠️ Limitations**")
                        st.write(summary.get("limitations", ""))
                        st.markdown("**🔭 Research Gap**")
                        st.write(summary.get("research_gap", ""))
            else:
                st.error("Could not summarize. Try another PDF.")