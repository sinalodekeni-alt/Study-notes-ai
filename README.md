# Study-notes-ai

This repository is a free AI student study notes generator for both highschool and tertiary (college and university) students that need assistance with understanding their school work.

## Features
- Study notes, flashcards and quizzes matched to your level (high school, college, advanced)
- Add content by pasting text, uploading a PDF or text file, using a YouTube transcript, or recording your voice (short clips)
- Chat with your notes
- Download notes as PDF or text
- Optional accounts with saved notes and folders (Supabase)

## Project structure
```
├─ app.py              # The whole Streamlit app
├─ requirements.txt    # Python packages
├─ .streamlit/
│  └─ config.toml      # Colours and theme
├─ .gitignore
├─ LICENSE             # MIT
└─ README.md
```

## Run it yourself
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
Create a `.env` file with:
```
ANTHROPIC_API_KEY=your-key
SUPABASE_URL=your-project-url
SUPABASE_KEY=your-publishable-key
```
The Supabase lines are optional (they turn on logins and saved notes). Never commit your `.env` file.

## Deploy
Use Streamlit Community Cloud: connect this repo, set the main file to `app.py`, and add the same three keys under Secrets.

## License
MIT
