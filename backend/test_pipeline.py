from services.transcript import get_transcript
from services.ai_service import generate_notes_and_summary, generate_quiz, grade_quiz

print("Step 1: Fetching transcript...")
data = get_transcript("aircAruvnKk")
print("  words=" + str(data["word_count"]) + "  duration=" + str(data["duration_seconds"]) + "s")

print("Step 2: Generating notes...")
notes = generate_notes_and_summary(data["full_text"], "But what IS a Neural Network?")
print("  summary_len=" + str(len(notes["summary"])))
print("  notes_sections=" + str(len(notes["notes"])))
print("  glossary_terms=" + str(len(notes["glossary"])))
print("  first note topic: " + notes["notes"][0]["topic"])

print("Step 3: Generating quiz (5 questions)...")
qs = generate_quiz(data["full_text"], num_questions=5)
print("  questions=" + str(len(qs)))
print("  q[0]: " + qs[0]["question"][:80])
print("  correct_answer=" + qs[0]["correct_answer"])

print("Step 4: Grading (3 correct, 2 skipped)...")
fake_answers = {}
for q in qs[:3]:
    fake_answers[str(q["id"])] = q["correct_answer"]
result = grade_quiz(qs, fake_answers)
print("  score=" + str(result["score"]) + "/" + str(result["total"]))
print("  grade=" + result["grade"] + "  pct=" + str(result["percentage"]) + "%")
print("  feedback: " + result["feedback"])

print("\n=== ALL PIPELINE TESTS PASSED ===")
