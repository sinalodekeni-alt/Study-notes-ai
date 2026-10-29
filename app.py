 import os
import re

import anthropic
import speech_recognition as sr
import streamlit as st
from dotenv import load_dotenv
from fpdf import FPDF
from pypdf import PdfReader
from youtube_transcript_api import YouTubeTranscriptApi

load_dotenv()

MODEL = "claude-sonnet-5-5"

LEVELS = {
    "High school": "a high school student. Use simple words and short sentences.",
    "College / University (first year)": "a first-year college student. Explain key terms clearly.",
    "Advanced (senior / postgraduate)": "an advanced student. Use precise academic language.",
}

TASKS = {
    "📝 Study notes": "Write clear, organised study notes with headings and bullet points. "
    "End with a short 'Key terms' list.",
    "🃏 Flashcards": "Create 10 flashcards. Format each one as:\nQ: question\nA: answer",
    "❓ Quiz": "Create an 8-question quiz with a mix of multiple choice and short answer. "
    "Put the answer key at the end.",
}

SOURCES = ["✍️ Paste text", "📄 Upload PDF", "▶️ YouTube link", "🎙️ Record voice"]


def generate(content: str, level: str, task: str) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    prompt = (
        f"You are a study helper for {LEVELS[level]}\n\n"
        f"Task: {TASKS[task]}\n\n"
        "Only use the content below. Do not invent facts.\n\n"
        f"CONTENT:\n{content}"
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def pdf_text(file) -> str:
    return "\n".join(p.extract_text() or "" for p in PdfReader(file).pages)


def youtube_text(url: str) -> str:
    if "v=" in url:
        video_id = url.split("v=")[-1].split("&")[0]
    else:
        video_id = url.rstrip("/").split("/")[-1].split("?")[0]
    transcript = YouTubeTranscriptApi().fetch(video_id)
    return " ".join(s.text for s in transcript)


def audio_text(audio) -> str:
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio) as source:
        data = recognizer.record(source)
    return recognizer.recognize_google(data)


def parse_cards(text: str):
    cards, question = [], None
    for line in text.replace("*", "").split("\n"):
        line = line.strip()
        q = re.match(r"^(?:\d+[.)]\s*)?Q\d*:\s*(.*)", line, re.I)
        a = re.match(r"^A\d*:\s*(.*)", line, re.I)
        if q:
            question = q.group(1)
        elif a and question:
            cards.append((question, a.group(1)))
            question = None
    return cards


def clean_for_pdf(text: str) -> str:
    swaps = {
        "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2022": "-", "\u2026": "...",
    }
    for old, new in swaps.items():
        text = text.replace(old, new)
    text = text.replace("**", "").replace("#", "").replace("`", "")
    return text.encode("latin-1", "replace").decode("latin-1")


def make_pdf(title: str, text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, clean_for_pdf(title), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", size=11)
    for line in clean_for_pdf(text).split("\n"):
        pdf.multi_cell(0, 6, line if line.strip() else " ", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


st.set_page_config(page_title="Study-notes-ai", page_icon="📚")

st.markdown(
    """
<style>
.hero {background: linear-gradient(135deg, #7C3AED, #06B6D4); padding: 1.4rem 1.2rem;
       border-radius: 18px; color: white; margin-bottom: 1rem;}
.hero h1 {color: white; margin: 0; font-size: 1.9rem; padding: 0;}
.hero p {margin: .4rem 0 0; opacity: .95;}
div.stButton > button {width: 100%; border-radius: 12px; font-weight: 700; padding: .7rem 0;}
div[data-testid="stExpander"] {border-radius: 12px; border: 1px solid #DDD6FE;}
</style>
<div class="hero">
  <h1>📚 Study-notes-ai</h1>
  <p>Turn lectures, PDFs, videos and voice notes into study material made for your level.</p>
</div>
""",
    unsafe_allow_html=True,
)

level = st.selectbox("🎓 Your level", list(LEVELS.keys()))
task = st.radio("🎯 What do you want?", list(TASKS.keys()), horizontal=True)
source = st.radio("📥 Where is your content from?", SOURCES, horizontal=True)

content = ""
try:
    if "Paste" in source:
        content = st.text_area("Paste your content here", height=250)
    elif "PDF" in source:
        pdf = st.file_uploader("Upload a PDF", type="pdf")
        if pdf:
            content = pdf_text(pdf)
    elif "YouTube" in source:
        link = st.text_input("YouTube link")
        if link:
            content = youtube_text(link)
    else:
        recording = st.audio_input("Tap to record")
        if recording:
            content = audio_text(recording)
            st.text_area("What I heard (you can edit this)", content, height=150)
except Exception as e:
    st.error(f"Could not read that source: {e}")

if st.button("✨ Generate"):
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.error("No API key found. Add ANTHROPIC_API_KEY to your Secrets.")
    elif not content.strip():
        st.warning("Please add some content first.")
    else:
        with st.spinner("Working on it..."):
            try:
                st.session_state["result"] = generate(content[:30000], level, task)
                st.session_state["task"] = task
                st.balloons()
            except Exception as e:
                st.error(f"Something went wrong: {e}")

result = st.session_state.get("result")
if result:
    saved_task = st.session_state.get("task", "")
    st.divider()
    st.subheader(saved_task)

    if "Flashcards" in saved_task:
        cards = parse_cards(result)
        if cards:
            st.caption("Tap a card to reveal the answer 👇")
            for i, (q, a) in enumerate(cards, 1):
                with st.expander(f"🃏 {i}. {q}"):
                    st.success(a)
        else:
            st.markdown(result)
    else:
        st.markdown(result)

    st.markdown("### ⬇️ Download")
    col1, col2 = st.columns(2)
    try:
        col1.download_button(
            "📄 PDF",
            make_pdf("Study-notes-ai", result),
            file_name="study-material.pdf",
            mime="application/pdf",
        )
    except Exception:
        col1.caption("PDF not available for this one.")
    col2.download_button("📝 Text file", result, file_name="study-material.txt")
