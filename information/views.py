from django.shortcuts import render
from django.shortcuts import render

def index(request):
    return render(request, 'information/index.html')

# def early(request):
#     return render(request, 'information/early.html')

# def mid(request):
#     return render(request, 'information/mid.html')

# def late(request):
#     return render(request, 'information/late.html')

from django.shortcuts import render
from .services.pregnancy_data import PREGNANCY_DATA
from .constants import EARLY_WEEKS, MID_WEEKS, LATE_WEEKS

def early(request):
    week = request.GET.get('week')
    selected = int(week) if week else None

    context = {
        'weeks': EARLY_WEEKS,
        'selected_week': selected,
        'info': PREGNANCY_DATA.get(selected) if selected else None,
        'title': '임신 초기 (1~13주)',
    }
    return render(request, 'information/detail.html', context)


def mid(request):
    week = request.GET.get('week')
    selected = int(week) if week else None

    context = {
        'weeks': MID_WEEKS,
        'selected_week': selected,
        'info': PREGNANCY_DATA.get(selected) if selected else None,
        'title': '임신 중기 (14~27주)',
    }
    return render(request, 'information/detail.html', context)


def late(request):
    week = request.GET.get('week')
    selected = int(week) if week else None

    context = {
        'weeks': LATE_WEEKS,
        'selected_week': selected,
        'info': PREGNANCY_DATA.get(selected) if selected else None,
        'title': '임신 후기 (28~40주)',
    }
    return render(request, 'information/detail.html', context)
