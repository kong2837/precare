# K-EPDS 저장, 내보내기, 그래프

K-EPDS는 제목에 `EPDS`가 포함된 설문을 대상으로 합니다.
10개 문항의 등록된 `Answer.value`(0~3)를 합산하며,
역채점은 관리 화면에 입력된 선택지 점수를 그대로 사용합니다.
불완전한 제출, 복수 선택, 등록되지 않은 선택지, 점수 미설정 응답은 저장하지 않습니다.

- 총점: 기존 `user_survey.score` (0~30)
- 응답: 기존 `reply.content`
- 제출 당시 문항별 점수: 새 `reply.score`

제출 후 선택지 점수를 변경해도 이미 저장된 총점과 문항별 점수는 바뀌지 않습니다.
진단 분류나 임계값에 따른 안내는 추가하지 않았습니다.

## 적용

```sh
venv/bin/python manage.py migrate --settings=apop2.settings_local
```

운영에서는 기존 운영 설정으로 `python manage.py migrate`를 실행한 뒤 웹 프로세스를 재시작합니다.

과거에 점수 없이 저장된 K-EPDS 응답이 있다면 아래 명령으로 대상 건수를 먼저 확인합니다.
현재 선택지의 점수를 사용하므로, 과거 설문과 선택지 점수가 일치하는지 확인하고 적용합니다.
불완전하거나 이미 일부 점수가 저장된 응답은 자동 계산에서 제외됩니다.

```sh
venv/bin/python manage.py backfill_epds_scores --settings=apop2.settings_local
venv/bin/python manage.py backfill_epds_scores --apply --settings=apop2.settings_local
```

## 설문결과보기 및 설문결과다운로드

Fitbit 및 Huami 참여자관리의 **설문** 컬럼에서 확인합니다.

- **설문결과보기**: K-EPDS를 선택하면 제출 시각별 총점과 문항 순서에 따른 응답·문항별 점수가 표시됩니다.
- 해당 설문의 **csv 다운로드**: 작성시간, 문항별 응답, K-EPDS 총점을 포함합니다.
- **설문결과다운로드**: 기존 Excel 파일의 K-EPDS 시트에 작성시간, 10개 문항의 응답, 총점을 포함합니다.

건강데이터 컬럼의 CSV에는 건강 측정 데이터만 포함합니다.

## 그래프

관리자의 Fitbit/Huami 참여자 상세 화면과 로그인한 참여자 홈에서 `epds` 그래프를 조회합니다.
기존 API의 접근 권한(본인 또는 관리자)을 사용합니다.
축 범위는 0~30이며, 기존 집계 방식대로 주간은 최고점,
월간은 일별 평균 → ISO 주별 평균 → 월 평균으로 계산합니다.
K-EPDS 기록이 없는 기간은 점수 0으로 간주하지 않습니다.
관리자는 주간·월간 그래프의 점을 클릭해 해당 기간의 개별 응답과 문항별 점수를 확인합니다.
