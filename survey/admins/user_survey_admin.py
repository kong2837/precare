from django.contrib import admin

from survey.models import UserSurvey, Reply

class ReplyInline(admin.StackedInline):
    """UserSurvey 어드민에서 Reply들을 나타내기 위한 클래스
    """    
    model = Reply
    extra = 0


class UserSurveyAdmin(admin.ModelAdmin):
    """UserSurvey 모델 어드민
    """    
    fields = ['user', 'survey', 'score']
    readonly_fields = ['score']
    list_display = ['user', 'survey', 'score', 'create_at']
    ordering = ['user', 'create_at']
    search_fields = ['user__username', 'survey__title']
    search_help_text = "유저나 설문조사를 검색할 수 있습니다."
    
    inlines = [ReplyInline]

admin.site.register(UserSurvey, UserSurveyAdmin)
