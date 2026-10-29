import os

import anthropic
import speech_recognition as sr
import streamlit as st
from dotenv import load_dotenv
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
    "Study notes": "Write clear, organised study notes with headings and bullet points. "
    "End with a short 'Key terms' list.",
    "Flashcards": "Create 10 flashcards. Format each one as:\nQ: question\nA: answer",
    "Quiz": "Create an 8-question quiz with a mix of multiple choice and short answer. "
    "Put the answer key at the end.",
}


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


st.set_page_config(page_title="Study-notes-ai", page_icon="📚")
st.title("📚 Study-notes-ai")
st.caption("Turn lecture notes, PDFs, videos or voice recordings into study material for your level.")

level = st.selectbox("Your academic level", list(LEVELS.keys()))
task = st.radio("What do you want?", list(TASKS.keys()), horizontal=True)
source = st.radio(
    "Where is your content from?",
    ["Paste text", "Upload PDF", "YouTube link", "Record voice"],
    horizontal=True,
)

content = ""
try:
    if source == "Paste text":
        content = st.text_area("Paste your content here", height=250)
    elif source == "Upload PDF":
        pdf = st.file_uploader("Upload a PDF", type="pdf")
        if pdf:
            content = pdf_text(pdf)
    elif source == "YouTube link":
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

if st.button("Generate"):
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.error("No API key found. Add ANTHROPIC_API_KEY to your Secrets.")
    elif not content.strip():
        st.warning("Please add some content first.")
    else:
        with st.spinner("Working on it..."):
            try:
                result = generate(content[:30000], level, task)
                st.markdown(result)
                st.download_button("Download", result, file_name="study-material.txt")
            except Exception as e:
                st.error(f"Something went wrong: {e}")
