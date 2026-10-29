import google.generativeai as genai

# Configure using the student's free API key
genai.configure(api_key="STUDENT_GEMINI_API_KEY")

def generate_study_materials(transcript_text, academic_level):
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    You are an expert tutor. Analyze the following transcript: "{transcript_text}".
    The target student is currently at academic level: {academic_level}.
    
    Provide:
    1. A simplified, structured summary with extra contextual information.
    2. 5 digital flashcards (Question/Answer format).
    3. 3 exam-level multiple-choice or short-answer questions tailored strictly to a {academic_level} difficulty profile.
    """
    response = model.generate_content(prompt)
    return response.text

