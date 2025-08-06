from datetime import timedelta
from django.utils.timezone import now
import requests
from requests.auth import HTTPBasicAuth
from django.conf import settings


def refresh_token(account):
    """FitbitAccount 인스턴스를 이용해 access_token 갱신"""
    url = "https://api.fitbit.com/oauth2/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "refresh_token",
        "client_id": settings.FITBIT_CLIENT_ID,
        "refresh_token": account.refresh_token
    }

    response = requests.post(
        url,
        headers=headers,
        data=data,
        auth=HTTPBasicAuth(settings.FITBIT_CLIENT_ID, settings.FITBIT_CLIENT_SECRET)
    )

    if response.status_code == 200:
        new_tokens = response.json()

        # account 필드 업데이트
        account.access_token = new_tokens["access_token"]
        account.refresh_token = new_tokens["refresh_token"]
        account.expires_at = now() + timedelta(seconds=new_tokens["expires_in"])
        account.scope = new_tokens.get("scope", account.scope)
        account.token_type = new_tokens.get("token_type", "Bearer")

        account.save()
        print(f"✅ {account.user.username}의 토큰 갱신 완료")
        return True
    else:
        print("❌ 토큰 갱신 실패:", response.status_code, response.text)
        return False
