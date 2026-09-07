GOLDEN_QUESTIONS = [
    "What is the borrower rating?",
    "What is the borrower outlook?",
]

def stub_llm(text, question):
    """
    KISS stand-in for an LLM extractor.
    In production, replace this with a real model call.
    """
    text = text.lower()
    question = question.lower()

    if "rating" in question and "bbb-" in text:
        return "BBB-"

    if "outlook" in question:
        if "stable" in text:
            return "stable"
        if "negative" in text:
            return "negative"

    return "UNKNOWN"

def factual_guard(prev_text,curr_text):
    results = {}
    for q in GOLDEN_QUESTIONS:
        prev = stub_llm(prev_text, q)
        curr = stub_llm(curr_text, q)
        results[q] = {
            "prev": prev,
            "curr": curr,
            "match": prev == curr,
        }
    return results

if __name__ == "__main__":
    prev_car = """
    Borrower rating is BBB-.
    Outlook is stable.
    """

    curr_answer = """
    Borrower rating is BBB-.
    Outlook is negative.
    """
    result = factual_guard(prev_car, curr_answer)
    print(result)
    