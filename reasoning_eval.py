def stub_judge(context, curr_answer):
    """
    KISS stand-in for a smaller LLM judge.

    Returns PASS when the answer only uses reasons found
    in the supplied evidence, otherwise FAIL.
    """
    context = context.lower()
    answer = curr_answer.lower()

    unsupported_terms = [
        "management quality deteriorated",
        "customer concentration worsened",
    ]

    for term in unsupported_terms:
        if term in answer and term not in context:
            return "FAIL"

    return "PASS"


def reasoning_guard(context, curr_answer, judge_llm=stub_judge):
    """
    Production idea:
    send evidence + generated answer to a smaller judge model
    and ask whether the material reasoning is supported.

    For the interview demo, stub_judge keeps it deterministic.
    """
    return judge_llm(context, curr_answer)


if __name__ == "__main__":
    context = """
    Leverage increased and cash flow weakened.
    """

    curr_answer = """
    Credit quality weakened because leverage increased
    and management quality deteriorated.
    """

    result = reasoning_guard(context, curr_answer)
    print(result)
