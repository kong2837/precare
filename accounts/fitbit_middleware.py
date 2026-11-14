from django.contrib.auth import login
from fitbit.participants import active_participant


class FitbitParticipantSessionMiddleware:
    """Existing Fitbit sessions follow the active participant after replacement."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and not user.is_staff and not user.is_superuser and not hasattr(user, "huami"):
            account = getattr(user, "fitbit", None)
            if account is not None and account.participant_ended_at is not None:
                active = active_participant(account)
                login(request, active.user, backend=request.session.get("_auth_user_backend", "django.contrib.auth.backends.ModelBackend"))
        return self.get_response(request)
