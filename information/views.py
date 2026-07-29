from django.http import HttpResponseBadRequest
from django.shortcuts import render

from .constants import EARLY_WEEKS, MID_WEEKS, LATE_WEEKS
from .services.pregnancy_data import PREGNANCY_DATA


def index(request):
    return render(request, "information/index.html")


def get_valid_week(request, allowed_weeks, default_week):
    """
    week 파라미터를 정수로 변환하고 허용된 임신 주차인지 확인한다.

    week 파라미터가 없거나 빈 문자열이면 해당 구간의 첫 주차를 사용한다.
    잘못된 문자열이나 허용 범위 밖의 숫자는 400 응답으로 처리한다.
    """
    raw_week = request.GET.get("week")

    if raw_week in (None, ""):
        return default_week

    try:
        week = int(raw_week)
    except (TypeError, ValueError):
        return None

    if week not in allowed_weeks:
        return None

    return week


def early(request):
    selected = get_valid_week(
        request=request,
        allowed_weeks=EARLY_WEEKS,
        default_week=1,
    )

    if selected is None:
        return HttpResponseBadRequest("Invalid week.")

    context = {
        "weeks": EARLY_WEEKS,
        "selected_week": selected,
        "info": PREGNANCY_DATA.get(selected),
        "title": "임신 초기 (1~13주)",
    }

    return render(request, "information/detail.html", context)


def mid(request):
    selected = get_valid_week(
        request=request,
        allowed_weeks=MID_WEEKS,
        default_week=14,
    )

    if selected is None:
        return HttpResponseBadRequest("Invalid week.")

    context = {
        "weeks": MID_WEEKS,
        "selected_week": selected,
        "info": PREGNANCY_DATA.get(selected),
        "title": "임신 중기 (14~27주)",
    }

    return render(request, "information/detail.html", context)


def late(request):
    selected = get_valid_week(
        request=request,
        allowed_weeks=LATE_WEEKS,
        default_week=28,
    )

    if selected is None:
        return HttpResponseBadRequest("Invalid week.")

    context = {
        "weeks": LATE_WEEKS,
        "selected_week": selected,
        "info": PREGNANCY_DATA.get(selected),
        "title": "임신 후기 (28~40주)",
    }

    return render(request, "information/detail.html", context)