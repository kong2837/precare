from survey.models import Survey, Question, UserSurvey, Reply, SurveyQuestion, Answer
from django.db.models import Q

def __make_p_tag(origin: str) -> str:
    style = (
        'font-size:1.1rem; '
        'line-height:1.6; '
        'word-break:keep-all; '
        'text-align:center; '
        'padding:0 1rem;'
    )
    return f'<p style="{style}"><strong>{origin}</strong></p>'


def stress_result(scores: tuple) -> str:
    total = sum(scores)
    if total >= 16:
        return __make_p_tag(
            "심호흡을 한 후 잠깐 걸어 볼까요^^<br>"
            "그럼 이제 마음이 차분해지는 음악을 들어보세요♪<br>"
            "좋아하는 음악이면 됩니다.❤️️"
        )
    if total >= 10:
        return __make_p_tag("오늘 힘드셨군요.<br>잠시 앉아 심호흡을 해보세요.❤️️")
    if total >= 6:
        return __make_p_tag("하던 일을 멈추고 후~<br>심호흡을 해보세요.️❤️")
    return __make_p_tag("스트레스 점수가 낮습니다.<br>잘하셨어요.☺<br>짝짝짝 지금처럼 편안하게 지내세요.❤️")


def __check_score(scores: tuple, std: int) -> bool:
    return sum(scores) >= std


def pbras_result(scores: tuple) -> str:
    mon1 = (scores[0], scores[1], scores[6])
    mon2 = (scores[2], scores[3], scores[7])
    mon3 = (scores[4], scores[5])
    mon4 = (scores[8], scores[9])

    if __check_score(mon1, 3):
        return __make_p_tag("침상에서 안정을 취한 후, 증상이 계속되면 산과 진료를 받는 것을 추천합니다!")
    if __check_score(mon1, 2):
        return __make_p_tag("침상에 누워 안정을 취하세요.❤️")
    if __check_score(mon2, 3):
        return __make_p_tag("침대에 누워 안정을 취하세요.❤️")
    if __check_score(mon2, 2):
        return __make_p_tag("앉아서 물을 한잔 마시세요.❤️")
    if __check_score(mon3, 3):
        return __make_p_tag("틈틈이 앉아 물을 마시세요.❤️")
    if __check_score(mon4, 3):
        return __make_p_tag("물을 자주 마시고 심호흡을 해보세요.❤️")
    if __check_score(mon4, 2):
        return __make_p_tag("편안함을 주는 음악을 들으세요.❤️")
    return __make_p_tag("네 좋아요. 지금처럼 지내시면 됩니다.❤️")

def update_survey_scores():
    """기존 설문조사의 score가 저장되지 않은 유저 스트레스 점수 업데이트 함수"""
    user_surveys = UserSurvey.objects.filter(
        survey__title__icontains="임신스트레스 10문항"
    ) | UserSurvey.objects.filter(
        survey__title__icontains="QUIPP"
    ) | UserSurvey.objects.filter(
        survey__title__icontains="조기진통위험 10문항"
    )

    answers_dict = {
        a.description.strip().replace(" ", "").replace(".", "").replace("·", ""): a.value
        for a in Answer.objects.all()
    }

    for user_survey in user_surveys:
        try:
            replies = Reply.objects.filter(
                user_survey=user_survey
            ).order_by("survey_question__order")

            scores = []
            for reply in replies:
                desc_raw = reply.content or ""
                desc_cleaned = desc_raw.strip().replace(" ", "").replace(".", "").replace("·", "")

                score = answers_dict.get(desc_cleaned)

                if score is not None:
                    scores.append(score)
                else:
                    # 🔽 주관식 문항은 0점으로 처리 (QUIPP 설문인 경우)
                    if "QUIPP" in user_survey.survey.title:
                        scores.append(0)
                        print(f"[ℹ️] 주관식 문항 → 0점 처리: {desc_raw}")
                    else:
                        print(f"[❌] Answer 매칭 실패: {desc_raw}")

            total_score = sum(scores)
            user_survey.score = total_score
            user_survey.save()

            print(f"[✅] {user_survey.id} → 총 점수 {total_score} 저장 완료 ({user_survey.survey.title})")

        except Exception as e:
            print(f"[⚠️] 오류 발생 (user_survey={user_survey.id}): {e}")