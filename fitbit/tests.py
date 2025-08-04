import requests
import json

# 액세스 토큰 (실제 Bearer token 형태로 입력해야 함)
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIyM1FEUTYiLCJzdWIiOiJDSlhMN0oiLCJpc3MiOiJGaXRiaXQiLCJ0eXAiOiJhY2Nlc3NfdG9rZW4iLCJzY29wZXMiOiJ3aHIgd251dCB3cHJvIHd0ZW0gd3NsZSB3d2VpIHdhY3Qgd2xvYyB3cmVzIHdveHkiLCJleHAiOjE3NTQzMDk1MjgsImlhdCI6MTc1NDI4MDcyOH0.8w4cgXpx8ykAucHjQ5iq-YHLhc8aBgVMmvfZOKrJrSw"

# Fitbit API 요청 헤더
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}"
}

# 요청할 날짜 (2024년 6월 26일)
date = "2025-06-26"

# API 엔드포인트
url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{date}/1d/1min.json"

# 요청 보내기
response = requests.get(url, headers=headers)

# 결과 확인
if response.status_code == 200:
    data = response.json()
    print("심박수 1분 단위 데이터:")
    for item in data["activities-heart-intraday"]["dataset"]:
        print(f"{item['time']} - {item['value']} bpm")
else:
    print("요청 실패:", response.status_code)
    print(response.text)
