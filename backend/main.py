import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from services.transcript import extract_video_id, get_transcript
from services.ai_service import generate_notes_and_summary, generate_quiz, grade_quiz, chat_about_video

load_dotenv()

app = FastAPI(title="YouTube Learning Assistant API", version="1.0.0")

# Allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Serve frontend static files
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# ─── Request / Response Models ────────────────────────────────────────────────

class VideoRequest(BaseModel):
    url: str
    transcript: str | None = None
    video_id: str | None = None
    word_count: int | None = None
    duration_seconds: int | None = None

class NotesRequest(BaseModel):
    transcript: str
    video_title: str = ""

class QuizGenerateRequest(BaseModel):
    transcript: str
    num_questions: int = 10

class QuizGradeRequest(BaseModel):
    questions: list
    user_answers: dict

class ChatRequest(BaseModel):
    transcript: str
    question: str
    history: list = []


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "cloud_host": bool(os.getenv("RENDER") or os.getenv("RAILWAY_ENVIRONMENT")),
        "transcript_mode": "gemini" if os.getenv("RENDER") else "youtube",
    }


@app.post("/api/process")
async def process_video(req: VideoRequest):
    """Extract video ID and fetch transcript from YouTube."""
    video_id = extract_video_id(req.url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL. Please check and try again.")

    # Fetch video title from oEmbed (no API key needed)
    title = ""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json",
                timeout=5,
            )
            if r.status_code == 200:
                title = r.json().get("title", "")
    except Exception:
        pass

    if req.transcript and req.transcript.strip():
        full_text = req.transcript.strip()
        transcript_data = {
            "full_text": full_text,
            "word_count": req.word_count or len(full_text.split()),
            "duration_seconds": req.duration_seconds or 0,
        }
    else:
        try:
            transcript_data = get_transcript(video_id)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    return {
        "video_id": video_id,
        "video_title": title,
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        "transcript": transcript_data["full_text"],
        "word_count": transcript_data["word_count"],
        "duration_seconds": transcript_data["duration_seconds"],
    }


@app.post("/api/notes")
async def get_notes(req: NotesRequest):
    """Generate AI notes, summary, and glossary from transcript."""
    if not req.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty.")
    try:
        result = generate_notes_and_summary(req.transcript, req.video_title)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")


@app.post("/api/quiz/generate")
async def create_quiz(req: QuizGenerateRequest):
    """Generate MCQ quiz questions from transcript."""
    if not req.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty.")
    num_q = max(5, min(req.num_questions, 20))
    try:
        questions = generate_quiz(req.transcript, num_q)
        return {"questions": questions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quiz generation failed: {str(e)}")


@app.post("/api/quiz/grade")
async def submit_quiz(req: QuizGradeRequest):
    """Grade submitted quiz answers."""
    if not req.questions:
        raise HTTPException(status_code=400, detail="No questions provided.")
    result = grade_quiz(req.questions, req.user_answers)
    return result


@app.post("/api/chat")
async def chat_video(req: ChatRequest):
    """Chat with AI about the video."""
    if not req.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty.")
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question is empty.")
    try:
        response_text = chat_about_video(req.transcript, req.question, req.history)
        return {"response": response_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI chat failed: {str(e)}")

# Serve frontend + API from one host (e.g. Render free tier)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        return {"status": "ok", "message": "Backend is running, but frontend folder not found."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
