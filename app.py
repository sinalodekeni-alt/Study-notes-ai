import os
import json
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from google import genai
from google.genai import errors

# Initialize FastAPI app
app = FastAPI(
    title="Study Notes & Adaptive Quiz AI API",
    version="1.0.0",
    description="Backend API for AI-powered study notes and adaptive multi-format learning quizzes."
)

# Enable CORS for Next.js frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Google GenAI Client
# Ensure GEMINI_API_KEY is configured in your environment variables
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


# --- Pydantic Models for Request/Response Validation ---

class NoteRequest(BaseModel):
    topic: str = Field(..., description="The study topic or rough notes provided by the student.")
    detail_level: Optional[str] = Field("comprehensive", description="Level of detail: concise, comprehensive, or bulleted.")

class QuizRequest(BaseModel):
    topic: str
    performance_score: Optional[float] = Field(0.7, description="Past performance ratio (0.0 to 1.0) to scale difficulty.")
    current_difficulty: Optional[str] = Field("Intermediate", description="Beginner, Intermediate, Advanced, or Expert.")

class QuizSubmission(BaseModel):
    user_answers: List[str]
    correct_answers: List[str]


# --- Helper Function for Gemini AI Calls ---

def call_gemini(prompt: str, expect_json: bool = False):
    """Safely calls the Gemini model and handles parsing and errors."""
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text_output = response.text.strip()

        if expect_json:
            # Clean markdown code blocks if the model wrapped the JSON
            if text_output.startswith("```"):
                text_output = text_output.split("```")[1]
                if text_output.startswith("json"):
                    text_output = text_output[4:]
                text_output = text_output.strip()
            return json.loads(text_output)

        return text_output

    except errors.APIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API Error: {getattr(e, 'message', str(e))}"
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse structured JSON response from the AI model."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


# --- API Routes ---

@app.get("/")
def health_check():
    return {"status": "healthy", "service": "Study Notes AI Backend"}


@app.post("/api/notes")
def generate_study_notes(payload: NoteRequest):
    """Generates structured markdown study notes based on user input topic."""
    if not payload.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be empty.")

    prompt = f"""
    Create structured, engaging, and comprehensive study notes for the topic: '{payload.topic}'.
    Format the output cleanly in Markdown with clear headings, key terms highlighted, and bullet points.
    Level of detail: {payload.detail_level}.
    """
    
    notes_markdown = call_gemini(prompt, expect_json=False)
    return {"topic": payload.topic, "notes": notes_markdown}


@app.post("/api/quiz")
def generate_adaptive_quiz(payload: QuizRequest):
    """
    Generates an adaptive quiz that automatically scales in question complexity 
    based on the student's performance metrics and current difficulty level.
    """
    # Dynamic difficulty adjustment based on performance score
    difficulty = payload.current_difficulty
    if payload.performance_score >= 0.85 and difficulty == "Beginner":
        difficulty = "Intermediate"
    elif payload.performance_score >= 0.85 and difficulty == "Intermediate":
        difficulty = "Advanced"
    elif payload.performance_score < 0.4 and difficulty in ["Advanced", "Intermediate"]:
        difficulty = "Beginner"

    prompt = f"""
    Create a 4-question multiple-choice adaptive quiz on the topic '{payload.topic}' tailored precisely for a {difficulty} skill level.
    Return ONLY a valid JSON array matching this exact schema with no extra text or markdown wrappers outside the JSON:
    [
      {{
        "id": 1,
        "question": "Question text here?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "answer": "Exact correct option string",
        "explanation": "Brief rationale for the correct answer."
      }}
    ]
    """

    quiz_data = call_gemini(prompt, expect_json=True)
    return {
        "topic": payload.topic,
        "assigned_difficulty": difficulty,
        "quiz": quiz_data
    }


@app.post("/api/quiz/evaluate")
def evaluate_quiz(payload: QuizSubmission):
    """Evaluates user answers against correct answers and calculates metrics."""
    if len(payload.user_answers) != len(payload.correct_answers):
        raise HTTPException(status_code=400, detail="Mismatch between user answers and correct answers count.")

    score = sum(1 for u, c in zip(payload.user_answers, payload.correct_answers) if u.strip().lower() == c.strip().lower())
    total = len(payload.correct_answers)
    percentage = (score / total) if total > 0 else 0.0

    # Determine recommended next step
    next_action = "maintain"
    if percentage >= 0.75:
        next_action = "scale_up"
    elif percentage < 0.5:
        next_action = "review_notes"

    return {
        "score": score,
        "total": total,
        "percentage": percentage,
        "next_action": next_action
}
