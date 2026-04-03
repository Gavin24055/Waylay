"""
J — Onboarding Module
Picks and asks one unanswered onboarding question per day, naturally.
"""

import logging

logger = logging.getLogger("j.proactive.onboarding")

# Natural conversation starters for each question
QUESTION_INTROS = {
    1: "Hey, random thought — ",
    2: "I've been meaning to ask — ",
    3: "Something I was curious about — ",
    4: "Quick one for you — ",
    5: "Real talk for a sec — ",
    6: "I was thinking about this — ",
    7: "So I'm curious — ",
    8: "Been wanting to ask — ",
    9: "This just came to mind — ",
    10: "Oh, one thing — ",
}


def get_onboarding_prompt(structured_memory) -> str | None:
    """
    Get the next unanswered onboarding question, phrased naturally.
    Returns None if all questions have been answered.
    """
    if not structured_memory:
        return None

    question_data = structured_memory.get_next_onboarding_question()
    if not question_data:
        logger.info("All onboarding questions have been answered")
        return None

    q_id = question_data["id"]
    question = question_data["question"]
    intro = QUESTION_INTROS.get(q_id, "Hey, ")

    prompt = f"{intro}{question.lower()}"
    logger.info("Onboarding question #%d: %s", q_id, question)
    return prompt


def process_onboarding_answer(question_id: int, answer: str,
                                structured_memory=None, episodic_memory=None):
    """
    Store the answer from an onboarding question.
    Saves to SQLite and ChromaDB for future recall.
    """
    if structured_memory:
        structured_memory.mark_question_answered(question_id, answer)
        logger.info("Onboarding question #%d answered", question_id)

    if episodic_memory:
        episodic_memory.save(
            content=f"Onboarding answer: {answer}",
            tags=["onboarding", "personal"],
            metadata={"question_id": str(question_id)},
        )
