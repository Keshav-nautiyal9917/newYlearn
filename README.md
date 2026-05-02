# YLearn — AI YouTube Learning Assistant

Transform **any YouTube video** into smart notes, a summary, key terms, and a scored mock test — powered by Google Gemini AI.

---

## Features

| Feature | Description |
|---------|-------------|
| 📝 Smart Notes | Topic-organized bullet-point notes from the video |
| 📄 AI Summary | 4–6 paragraph comprehensive summary |
| 📚 Glossary | 8–12 key terms with definitions |
| 🧠 Mock Test | 10 AI-generated MCQ questions with a 20-minute timer |
| 🏆 Graded Results | Score, letter grade (A+→F), and question-by-question review |

---

## Quick Start

### 1. Prerequisites
- Python 3.10+
- A free **Google Gemini API key** → https://aistudio.google.com/app/apikey

### 2. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 3. Configure API Key
```bash
# Copy the example env file
copy .env.example .env

# Open .env and paste your Gemini API key
# GEMINI_API_KEY=AIza...your_key_here
```

### 4. Run the Server
```bash
cd backend
python main.py
```

The app will be available at **http://localhost:8000**

---

## Project Structure

```
project/
├── backend/
│   ├── main.py                  # FastAPI server + all API routes
│   ├── services/
│   │   ├── transcript.py        # YouTube transcript extraction
│   │   └── ai_service.py        # Gemini AI: notes, quiz, grading
│   ├── requirements.txt
│   └── .env.example
│
└── frontend/
    ├── index.html               # Home: YouTube URL input
    ├── notes.html               # Notes, Summary & Glossary
    ├── quiz.html                # Interactive timed quiz
    ├── results.html             # Score, grade & review
    ├── style.css                # Design system (dark/glass)
    └── app.js                   # Shared JS logic
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/process` | Extract transcript from YouTube URL |
| POST | `/api/notes` | Generate notes, summary & glossary |
| POST | `/api/quiz/generate` | Generate MCQ quiz questions |
| POST | `/api/quiz/grade` | Grade submitted answers |

---

## Notes

- YouTube videos **must have captions** (auto-generated or manual). Videos without any subtitles cannot be processed.
- The Gemini free tier supports up to **15 requests/minute** — more than enough for normal use.
- Quiz timer is set to **20 minutes** by default.
