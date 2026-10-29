import json
import os
import re

import anthropic
import speech_recognition as sr
import streamlit as st
from dotenv import load_dotenv
from fpdf import FPDF
from pypdf import PdfReader
from youtube_transcript_api import YouTubeTranscriptApi

try:
    from supabase import create_client
except ImportError:
    create_client = None

load_dotenv()

MODEL = "claude-sonnet-5-5"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DB_ENABLED = bool(create_client and SUPABASE_URL and SUPABASE_KEY)

LEVELS = {
    "High school": "a high school student. Use simple words and short sentences.",
    "College / University (first year)": "a first-year college student. Explain key terms clearly.",
    "Advanced (senior / postgraduate)": "an advanced student. Use precise academic language.",
}

SOURCES = {
    "paste": "✍️ Paste text",
    "pdf": "📄 PDF",
    "youtube": "▶️ YouTube",
    "voice": "🎙️ Record",
}

NOTES_TASK = (
    "Create rich, easy-to-scan study notes in Markdown. Start with a one-line summary. "
    "Use emoji section headings (## 📌 Heading), short bullet points, and a 'Key terms' "
    "table with the columns Term | Meaning. Add callouts for the most important ideas "
    "using lines that start with '> 💡 Remember:'. End with a '✅ Quick recap' of "
    "3 to 5 bullets."
)

CARDS_TASK = "Create 10 flashcards. Format each one as:\nQ: question\nA: answer"

QUIZ_TASK = (
    "Create 8 multiple-choice questions. Reply with ONLY valid JSON and nothing else, "
    'as a list like: [{"q": "question", "options": ["A", "B", "C", "D"], '
    '"answer": 0, "why": "short explanation"}] where answer is the index (0 to 3) '
    "of the correct option."
)


def ask(system: str, messages: list, max_tokens: int = 2000) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    return response.content[0].text


def run_task(task: str, content: str, level: str, max_tokens: int = 2000) -> str:
    system = f"You are a friendly study helper for {LEVELS[level]}"
    prompt = f"Task: {task}\n\nOnly use the content below. Do not invent facts.\n\nCONTENT:\n{content}"
    return ask(system, [{"role": "user", "content": prompt}], max_tokens)


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


def parse_quiz(raw: str):
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    return json.loads(raw)


def clean_for_pdf(text: str) -> str:
    swaps = {
        "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2022": "-", "\u2026": "...",
    }
    for old, new in swaps.items():
        text = text.replace(old, new)
    text = text.replace("**", "").replace("#", "").replace("`", "")
    return text.encode("latin-1", "ignore").decode("latin-1")


def make_pdf(title: str, text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, clean_for_pdf(title), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", size=11)
    for line in clean_for_pdf(text).split("\n"):
        if line.startswith(">"):
            line = line[1:].strip()
        pdf.multi_cell(0, 6, line if line.strip() else " ", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def default_title(text: str) -> str:
    for line in text.split("\n"):
        line = re.sub(r"[#*>_`]", "", line).strip()
        if line:
            return line[:60]
    return "My notes"


def clear_quiz_answers():
    for k in list(st.session_state.keys()):
        if k.startswith("quiz_"):
            del st.session_state[k]


def get_client():
    # One client per browser session, so logins are never shared between users.
    if "sb" not in st.session_state:
        st.session_state["sb"] = create_client(SUPABASE_URL, SUPABASE_KEY)
    return st.session_state["sb"]


def load_into_session(data: dict):
    clear_quiz_answers()
    level = data.get("level") if data.get("level") in LEVELS else list(LEVELS.keys())[0]
    st.session_state.update(
        content=data["content"],
        level=level,
        notes=data["notes"],
        cards=data.get("cards"),
        quiz=data.get("quiz"),
        chat=[],
        note_id=data["id"],
    )


def account_panel():
    logged_in = bool(st.session_state.get("user"))
    with st.expander("👤 Account & saved notes", expanded=not logged_in):
        if not DB_ENABLED:
            st.caption("Saving isn't set up yet. Add SUPABASE_URL and SUPABASE_KEY to your Secrets.")
            return

        if not logged_in:
            login_tab, signup_tab = st.tabs(["Log in", "Sign up"])
            with login_tab:
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_pw")
                ok = False
                if st.button("Log in", key="do_login"):
                    try:
                        res = get_client().auth.sign_in_with_password(
                            {"email": email, "password": password}
                        )
                        st.session_state["user"] = res.user.email
                        ok = True
                    except Exception as e:
                        st.error(f"Could not log in: {e}")
                if ok:
                    st.rerun()
            with signup_tab:
                email2 = st.text_input("Email", key="signup_email")
                password2 = st.text_input(
                    "Password (at least 6 characters)", type="password", key="signup_pw"
                )
                ok = False
                if st.button("Create account", key="do_signup"):
                    try:
                        res = get_client().auth.sign_up({"email": email2, "password": password2})
                        if res.session:
                            st.session_state["user"] = email2
                            ok = True
                        else:
                            st.info("Check your email to confirm your account, then log in.")
                    except Exception as e:
                        st.error(f"Could not sign up: {e}")
                if ok:
                    st.rerun()
            return

        st.caption(f"Signed in as {st.session_state['user']}")
        try:
            saved = (
                get_client()
                .table("notes")
                .select("id,title,folder,created_at")
                .order("created_at", desc=True)
                .execute()
                .data
            )
        except Exception as e:
            st.error(f"Could not load your notes: {e}")
            saved = []

        folders = sorted({n["folder"] for n in saved})
        choice = st.selectbox("📁 Folder", ["All"] + folders, key="folder_filter")
        shown = [n for n in saved if choice == "All" or n["folder"] == choice]
        if not shown:
            st.caption("No saved notes here yet.")

        opened = None
        for n in shown:
            if st.button(f"📄 {n['title']}  ·  {n['created_at'][:10]}", key=f"open_{n['id']}"):
                opened = n["id"]
        if opened:
            ok = False
            try:
                data = (
                    get_client().table("notes").select("*").eq("id", opened).single().execute().data
                )
                load_into_session(data)
                st.session_state["flash"] = "Opened your saved note ✅"
                ok = True
            except Exception as e:
                st.error(f"Could not open that note: {e}")
            if ok:
                st.rerun()

        if st.button("Log out", key="logout"):
            try:
                get_client().auth.sign_out()
            except Exception:
                pass
            for k in ["sb", "user", "note_id"]:
                st.session_state.pop(k, None)
            st.rerun()


def save_panel():
    if not DB_ENABLED:
        return
    if not st.session_state.get("user"):
        st.info("🔐 Log in (at the top of the page) to save these notes.")
        return

    note_id = st.session_state.get("note_id")
    with st.expander("💾 Save to my notes", expanded=note_id is None):
        if note_id:
            st.caption("This note is saved. Update it to include new flashcards or a quiz.")
            col1, col2 = st.columns(2)
            ok = False
            if col1.button("💾 Update", key="update_note"):
                try:
                    get_client().table("notes").update(
                        {
                            "notes": st.session_state["notes"],
                            "cards": st.session_state.get("cards"),
                            "quiz": st.session_state.get("quiz"),
                        }
                    ).eq("id", note_id).execute()
                    st.session_state["flash"] = "Updated ✅"
                    ok = True
                except Exception as e:
                    st.error(f"Could not update: {e}")
            if col2.button("🗑️ Delete", key="delete_note"):
                try:
                    get_client().table("notes").delete().eq("id", note_id).execute()
                    st.session_state.pop("note_id", None)
                    st.session_state["flash"] = "Deleted 🗑️"
                    ok = True
                except Exception as e:
                    st.error(f"Could not delete: {e}")
            if ok:
                st.rerun()
        else:
            notes_text = st.session_state["notes"]
            title = st.text_input(
                "Title", value=default_title(notes_text), key=f"title_{abs(hash(notes_text))}"
            )
            folder = st.text_input("📁 Folder", value="General", key="save_folder")
            ok = False
            if st.button("💾 Save", key="save_note"):
                try:
                    res = (
                        get_client()
                        .table("notes")
                        .insert(
                            {
                                "title": title.strip() or "My notes",
                                "folder": folder.strip() or "General",
                                "level": st.session_state["level"],
                                "content": st.session_state["content"],
                                "notes": notes_text,
                                "cards": st.session_state.get("cards"),
                                "quiz": st.session_state.get("quiz"),
                            }
                        )
                        .execute()
                    )
                    st.session_state["note_id"] = res.data[0]["id"]
                    st.session_state["flash"] = "Saved to your notes ✅"
                    ok = True
                except Exception as e:
                    st.error(f"Could not save: {e}")
            if ok:
                st.rerun()


st.set_page_config(page_title="Study-notes-ai", page_icon="📚")

st.markdown(
    """
<style>
.hero {background: linear-gradient(135deg, #7C3AED, #06B6D4); padding: 1.4rem 1.2rem;
       border-radius: 18px; color: white; margin-bottom: 1rem;}
.hero h1 {color: white; margin: 0; font-size: 1.9rem; padding: 0;}
.hero p {margin: .4rem 0 0; opacity: .95;}
div.stButton > button {width: 100%; border-radius: 14px; font-weight: 700; padding: .75rem 0;}
div[data-testid="stExpander"] {border-radius: 12px; border: 1px solid #DDD6FE;}
button[data-baseweb="tab"] {font-weight: 600;}
blockquote {border-left: 4px solid #7C3AED; background: #F5F3FF; padding: .4rem .8rem;
            border-radius: 8px;}
</style>
<div class="hero">
  <h1>📚 Study-notes-ai</h1>
  <p>Turn lectures, PDFs, videos and voice notes into study material made for your level.</p>
</div>
""",
    unsafe_allow_html=True,
)

st.session_state.setdefault("source", "paste")
st.session_state.setdefault("chat", [])

if st.session_state.get("flash"):
    st.success(st.session_state.pop("flash"))

account_panel()

level = st.selectbox("🎓 Your level", list(LEVELS.keys()))

st.markdown("**📥 Add your content**")
cols = st.columns(4)
for col, (key, label) in zip(cols, SOURCES.items()):
    is_selected = st.session_state["source"] == key
    if col.button(label, key=f"src_{key}", type="primary" if is_selected else "secondary"):
        st.session_state["source"] = key
        st.rerun()

source = st.session_state["source"]
content = ""
try:
    if source == "paste":
        content = st.text_area("Paste your content here", height=220)
    elif source == "pdf":
        pdf = st.file_uploader("Upload a PDF", type="pdf")
        if pdf:
            content = pdf_text(pdf)
    elif source == "youtube":
        link = st.text_input("YouTube link")
        if link:
            content = youtube_text(link)
    else:
        recording = st.audio_input("Tap to record (short clips work best)")
        if recording:
            content = audio_text(recording)
            st.text_area("What I heard (you can edit this)", content, height=150)
except Exception as e:
    st.error(f"Could not read that source: {e}")

if st.button("✨ Generate my notes", type="primary"):
    if not os.getenv("ANTHROPIC_API_KEY"):
        st.error("No API key found. Add ANTHROPIC_API_KEY to your Secrets.")
    elif not content.strip():
        st.warning("Please add some content first.")
    else:
        with st.spinner("Making your notes..."):
            try:
                notes = run_task(NOTES_TASK, content[:30000], level)
                clear_quiz_answers()
                st.session_state.update(
                    content=content[:30000],
                    level=level,
                    notes=notes,
                    cards=None,
                    quiz=None,
                    chat=[],
                    note_id=None,
                )
                st.balloons()
            except Exception as e:
                st.error(f"Something went wrong: {e}")

if st.session_state.get("notes"):
    saved_level = st.session_state["level"]
    saved_content = st.session_state["content"]
    st.divider()

    save_panel()

    tab_notes, tab_cards, tab_quiz, tab_chat, tab_text = st.tabs(
        ["📝 Notes", "🃏 Flashcards", "❓ Quiz", "💬 Chat", "📜 Transcript"]
    )

    with tab_notes:
        st.markdown(st.session_state["notes"])
        col1, col2 = st.columns(2)
        try:
            col1.download_button(
                "📄 PDF",
                make_pdf("Study-notes-ai", st.session_state["notes"]),
                file_name="study-notes.pdf",
                mime="application/pdf",
                key="dl_pdf",
            )
        except Exception:
            col1.caption("PDF not available for this one.")
        col2.download_button(
            "📝 Text file", st.session_state["notes"], file_name="study-notes.txt", key="dl_txt"
        )

    with tab_cards:
        if not st.session_state.get("cards"):
            if st.button("🃏 Make flashcards", key="make_cards"):
                with st.spinner("Making flashcards..."):
                    try:
                        st.session_state["cards"] = run_task(CARDS_TASK, saved_content, saved_level)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Something went wrong: {e}")
        else:
            cards = parse_cards(st.session_state["cards"])
            if cards:
                st.caption("Tap a card to reveal the answer 👇")
                for i, (q, a) in enumerate(cards, 1):
                    with st.expander(f"🃏 {i}. {q}"):
                        st.success(a)
            else:
                st.markdown(st.session_state["cards"])
            st.download_button(
                "📝 Download flashcards",
                st.session_state["cards"],
                file_name="flashcards.txt",
                key="dl_cards",
            )

    with tab_quiz:
        if not st.session_state.get("quiz"):
            if st.button("❓ Make a quiz", key="make_quiz"):
                with st.spinner("Making your quiz..."):
                    try:
                        raw = run_task(QUIZ_TASK, saved_content, saved_level, max_tokens=3000)
                        st.session_state["quiz"] = parse_quiz(raw)
                        st.rerun()
                    except Exception:
                        st.error("The quiz didn't come out right. Please try again.")
        else:
            quiz = st.session_state["quiz"]
            for i, item in enumerate(quiz):
                st.markdown(f"**{i + 1}. {item['q']}**")
                st.radio(
                    "Choose one",
                    item["options"],
                    index=None,
                    key=f"quiz_{i}",
                    label_visibility="collapsed",
                )
            if st.button("✅ Check my answers", key="check_quiz"):
                score = 0
                for i, item in enumerate(quiz):
                    correct = item["options"][item["answer"]]
                    if st.session_state.get(f"quiz_{i}") == correct:
                        score += 1
                    else:
                        st.error(f"Question {i + 1}: the answer is {correct}. {item.get('why', '')}")
                st.metric("Your score", f"{score} / {len(quiz)}")
                if score == len(quiz):
                    st.balloons()

    with tab_chat:
        st.caption("Ask anything about your material 👇")
        for message in st.session_state["chat"]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        question = st.chat_input("Ask a question about your notes...")
        if question:
            st.session_state["chat"].append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)
            system = (
                f"You are a friendly tutor for {LEVELS[saved_level]} "
                "Answer using ONLY the study material below. If the answer is not "
                f"in the material, say so.\n\nMATERIAL:\n{saved_content}"
            )
            try:
                answer = ask(system, st.session_state["chat"])
            except Exception as e:
                answer = f"Something went wrong: {e}"
            st.session_state["chat"].append({"role": "assistant", "content": answer})
            with st.chat_message("assistant"):
                st.markdown(answer)

    with tab_text:
        st.text_area("Your source text", saved_content, height=300, disabled=True)
