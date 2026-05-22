import os
import json
import re
import time
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Model preference list — tried in order until one works
_MODEL_PREFERENCE = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-flash-latest",
]

_model_cache: dict = {}


def _get_model(name: str):
    if name not in _model_cache:
        _model_cache[name] = genai.GenerativeModel(name)
    return _model_cache[name]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _clean_json(text: str) -> str:
    """Strip markdown code fences and leading/trailing whitespace."""
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    return text.strip()


def _parse_json_safe(raw: str):
    """Try to parse JSON; if that fails, extract the first JSON object/array."""
    cleaned = _clean_json(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Find the first { or [ and try from there
        brace = cleaned.find("{")
        bracket = cleaned.find("[")
        candidates = [c for c in [brace, bracket] if c != -1]
        if candidates:
            start = min(candidates)
            try:
                return json.loads(cleaned[start:])
            except json.JSONDecodeError:
                pass
        raise ValueError(
            f"Could not parse AI response as JSON. Snippet: {cleaned[:300]}"
        )


def _generate_with_fallback(prompt: str) -> str:
    """
    Try each model in _MODEL_PREFERENCE. On 429 (quota exhausted) wait briefly
    and move on. Raises RuntimeError if all models are exhausted.
    """
    last_err = None
    for model_name in _MODEL_PREFERENCE:
        try:
            model = _get_model(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            err_str = str(e)
            # Quota / rate-limit — try next model after a short pause
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                last_err = e
                time.sleep(2)
                continue
            # Any other error is re-raised immediately
            raise
    raise RuntimeError(
        f"All Gemini models are currently quota-limited. "
        f"Please wait a few minutes and try again. Last error: {last_err}"
    )


# ─── Public Functions ─────────────────────────────────────────────────────────

def generate_notes_and_summary(transcript: str, video_title: str = "") -> dict:
    """Generate structured notes, summary, and key terms from a transcript."""

    prompt = f"""You are an expert educational content creator.
Analyse the following YouTube video transcript and produce:

1. A comprehensive SUMMARY (4-6 paragraphs) covering the main ideas.
2. Structured NOTES organised by topic/section (bullet points, sub-bullets for details).
3. A GLOSSARY of 8-12 important key terms/concepts with brief definitions.

Video Title: {video_title or "(unknown)"}

Transcript:
{transcript[:12000]}

Respond ONLY with valid JSON (no markdown fences, no commentary) in this exact structure:
{{
  "summary": "Full summary text here...",
  "notes": [
    {{
      "topic": "Topic Title",
      "points": ["point 1", "point 2", "sub detail"]
    }}
  ],
  "glossary": [
    {{"term": "Term Name", "definition": "Clear definition here."}}
  ]
}}"""

    raw = _generate_with_fallback(prompt)
    return _parse_json_safe(raw)


def generate_quiz(transcript: str, num_questions: int = 10) -> list:
    """Generate MCQ quiz questions from a transcript."""

    prompt = f"""You are an expert educator.
Based on the following YouTube video transcript, create exactly {num_questions} multiple-choice questions to test understanding.

Rules:
- Questions must be based strictly on the video content.
- Each question has exactly 4 options (A, B, C, D).
- Only one option is correct.
- Include a brief explanation for the correct answer.
- Vary difficulty: mix easy, medium, and hard questions.
- Do NOT repeat similar questions.

Transcript:
{transcript[:12000]}

Respond ONLY with valid JSON (no markdown fences, no commentary) as a list:
[
  {{
    "id": 1,
    "question": "Question text here?",
    "options": {{
      "A": "Option A text",
      "B": "Option B text",
      "C": "Option C text",
      "D": "Option D text"
    }},
    "correct_answer": "A",
    "explanation": "Explanation of why A is correct."
  }}
]"""

    raw = _generate_with_fallback(prompt)
    result = _parse_json_safe(raw)

    # Unwrap if AI wrapped it in an object
    if isinstance(result, dict) and "questions" in result:
        result = result["questions"]
    if not isinstance(result, list):
        raise ValueError("AI returned unexpected quiz format.")

    # Guarantee sequential IDs
    for i, q in enumerate(result, 1):
        q["id"] = i

    return result


def grade_quiz(questions: list, user_answers: dict) -> dict:
    """Grade quiz answers and return score + detailed results."""
    results = []
    score = 0

    for q in questions:
        qid = str(q["id"])
        user_ans = user_answers.get(qid, None)
        correct = q["correct_answer"]
        is_correct = user_ans == correct

        if is_correct:
            score += 1

        results.append({
            "id": q["id"],
            "question": q["question"],
            "user_answer": user_ans,
            "correct_answer": correct,
            "is_correct": is_correct,
            "explanation": q.get("explanation", ""),
            "options": q.get("options", {}),
        })

    total = len(questions)
    percentage = round((score / total) * 100) if total > 0 else 0

    if percentage >= 90:
        grade = "A+"
        feedback = "Outstanding! You have an exceptional understanding of the material."
    elif percentage >= 80:
        grade = "A"
        feedback = "Excellent work! You have a strong grasp of the content."
    elif percentage >= 70:
        grade = "B"
        feedback = "Good job! You understand most of the key concepts."
    elif percentage >= 60:
        grade = "C"
        feedback = "Fair performance. Review the explanations to strengthen your understanding."
    elif percentage >= 50:
        grade = "D"
        feedback = "You passed, but there is room for improvement. Re-watch the video and try again."
    else:
        grade = "F"
        feedback = "Keep practising! Review the notes and re-attempt the quiz."

    return {
        "score": score,
        "total": total,
        "percentage": percentage,
        "grade": grade,
        "feedback": feedback,
        "results": results,
    }


def chat_about_video(transcript: str, question: str, history: list = None) -> str:
    """Answer a user's question about the video using the transcript and chat history."""
    if history is None:
        history = []
        
    # Format history into a string
    history_text = ""
    for msg in history[-6:]:  # Only keep last 6 messages for context limits
        role = "User" if msg.get("role") == "user" else "AI"
        history_text += f"{role}: {msg.get('content')}\n"

    prompt = f"""You are 'YLearn AI', an intelligent tutor helping a student understand a YouTube video.
Answer the user's question strictly based on the provided transcript. If the answer is not in the transcript, politely state that it wasn't covered in the video.

Transcript:
{transcript[:12000]}

Recent Conversation History:
{history_text}

User's Question: {question}

Provide a clear, concise, and helpful response. Do NOT use markdown code blocks or JSON, just return plain text or simple markdown formatting for readability.
"""

    return _generate_with_fallback(prompt)

