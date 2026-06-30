import requests
from datetime import timedelta

from django.conf import settings
from django.utils.timezone import now


def refresh_google_health_token(account):
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.GOOGLE_HEALTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_HEALTH_CLIENT_SECRET,
            "refresh_token": account.refresh_token,
            "grant_type": "refresh_token",
        },
    )

    if response.status_code != 200:
        print("❌ Google Health 토큰 갱신 실패")
        print(response.text)
        return False

    token_data = response.json()

    account.access_token = token_data["access_token"]
    account.expires_at = now() + timedelta(seconds=token_data["expires_in"])
    account.token_type = token_data.get("token_type", "Bearer")
    account.save(update_fields=["access_token", "expires_at", "token_type"])

    return True