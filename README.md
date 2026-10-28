# Study-notes-ai
This repository is a free AI student study notes generator for both highschool and tertiary (college and university)students that need assistance with understanding their school work
## Project structure
```
├─ .github/workflows/     # CI/CD pipelines (optional)
├─ backend/               # Core application logic
│  ├─ audio/              # Mic recording & live transcription
│  ├─ ingestion/          # PDF and YouTube parsing
│  ├─ ai_engine/          # LLM prompts, summarization, extra info
│  └─ study_tools/        # Flashcard & adaptive quiz generation
├─ app.py                 # Main entry point (Streamlit or Gradio UI)
├─ requirements.txt       # Free Python dependencies
├─ .gitignore
├─ README.md              # Project documentation & setup guide
└─ LICENSE                # Open-source license (e.g., MIT)
```

## Setup
```
python -m venv venv
venv\Scripts\activate
pip install streamlit anthropic python-dotenv
pip freeze > requirements.txt
```
