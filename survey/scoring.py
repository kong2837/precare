"""K-EPDS scoring uses configured Answer.value, including reverse scoring."""


def is_epds(title):
    return "EPDS" in title.upper()


def epds_answers(survey, post_data):
    questions = list(survey.surveyquestion_set.select_related("question").order_by("order", "pk"))
    if len(questions) != 10:
        raise ValueError("K-EPDS 설문은 10개 문항으로 구성되어야 합니다. 관리자에게 문의해주세요.")

    expected = {str(sq.question_id) for sq in questions}
    if {key for key in post_data if key.isdigit()} != expected:
        raise ValueError("K-EPDS의 모든 문항에 하나씩 응답해주세요.")

    answers = []
    for sq in questions:
        selected = post_data.getlist(str(sq.question_id))
        if len(selected) != 1:
            raise ValueError("각 문항에서 하나의 응답을 선택해주세요.")
        matches = list(sq.question.answers.filter(description=selected[0]))
        if len(matches) != 1 or matches[0].value not in (0, 1, 2, 3):
            raise ValueError("선택한 응답의 점수를 확인할 수 없습니다. 관리자에게 문의해주세요.")
        answers.append((sq, selected[0], matches[0].value))
    return answers


def score_label(title):
    if is_epds(title):
        return "K-EPDS 점수"
    if "임신스트레스 10문항" in title:
        return "스트레스 점수"
    if "조기진통위험 10문항" in title:
        return "조기진통 점수"
    if "QUIPP" in title:
        return "QUIPP 점수"
    return None
