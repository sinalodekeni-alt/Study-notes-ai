import os

import anthropic
import streamlit as st
from dotenv import load_dotenv

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


st.set_page_config(page_title="Study-notes-ai", page_icon="📚")
st.title("📚 Study-notes-ai")
