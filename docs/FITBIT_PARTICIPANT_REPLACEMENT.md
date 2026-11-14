# Fitbit 참여자 교체

Fitbit 대상자 관리의 마지막 열에 있는 빨간 `참여자 교체하기` 버튼을 사용한다.
새 이름과 실제 교체 일시(한국 시간, 분 단위)를 입력한 뒤, 별도 확인 창에서 최종 확인한다.
입력 화면의 첫 확인은 DB를 수정하지 않는다. 확인 정보는 관리자와 대상에 묶인
서명 값이며 10분 동안 유효하다. 최종 확인 창에서 Fitbit Sense 공동 계정 사용 여부를 확인하도록 안내한다. 이미 교체된 대상의 재제출은 거절한다.

## 데이터와 로그인

- 새 Django User PK, Profile, FitbitAccount를 생성한다. 이전 User PK와 프로필은 보존한다.
- 동일한 외부 계정 ID를 공유하되, 최초 FitbitAccount가 연결 정보와 수집의 기준이다.
- source_account와 participant_started_at/participant_ended_at로 연속된 사용 구간을 관리한다.
  시작 시각은 포함하고 종료 시각은 제외한다. 일시는 미래로 지정할 수 없다.
- 교체 시각 이후의 기존 건강 행은 timestamp, 설문은 create_at, 클릭 로그는 created_at을
  기준으로 새 사용자에게 재배정한다. 데이터나 설문 답변/행동 피드백을 복사하거나 삭제하지 않는다.
- 건강 데이터 재수집은 저장된 측정/기준 timestamp에 해당하는 참여자에게 배정한다.
  날짜별 요약값은 원래 저장 방식에 따른 날짜/시각을 사용한다.
- 이름 수정 이력은 해당 프로필에 대한 관리 이력으로 기존 사용자에게 보존한다.
  교체 이력에는 이전/신규 프로필, 당시 이름, 교체 시각, 처리 관리자, 처리 시각을 기록한다.
- 외부 연결 정보와 이메일은 유지할 수 있지만 생년월일, 임신 정보, 메모는 복사하지 않는다.
- OAuth 재로그인은 현재 참여자로 로그인한다. 기존 일반 참여자 세션도 다음 요청부터
  현재 참여자로 전환된다. 관리자 세션과 Huami 사용자는 전환하지 않는다.
- Huami 계정이 함께 연결된 사용자는 교체 대상에서 제외한다.
- 이전 참여자는 Fitbit 목록, 상세 화면, 설문, 로그, CSV 등 기존 관리자 기능으로 조회한다.
- Fitbit 참여자 상세 화면의 `참여자 교체 기록`을 펼치면 같은 연결 계정의 전체 교체 이력을
  확인할 수 있다. 이전/새 참여자 이름과 시스템 사용자 ID, 교체 일시, 처리 관리자와 처리
  시각을 표시하며 각 참여자의 상세 화면으로 이동할 수 있다. Huami 상세에는 표시하지 않는다.

## 적용

기존 저장소의 `huami/migrations/0009_alter_huamiaccount_research_year.py`가 참조하는
`0008_huamiaccount_research_year.py`는 이번 커밋 이전부터 Git에 없는 상태다.
서버에 기존 `0008` 파일이 있는지 먼저 확인하고 보존해야 한다. 해당 파일이 없으면
Fitbit만 대상으로 migrate하더라도 Django 마이그레이션 의존성 검사에서 중단된다.
이 경우 기존 배포본의 해당 파일을 복구한 뒤 진행하며, 적용 이력을 임의로 fake하지 않는다.
이번 변경에는 Huami 코드나 마이그레이션을 포함하지 않는다.

웹 서비스와 스케줄러를 함께 중지한 유지보수 구간에서 기존 배포 절차에 따라 DB 백업 후
`python manage.py showmigrations fitbit`로 서버의 적용 상태를 확인한 다음
`python manage.py migrate fitbit`를 실행하고, 같은 소스 버전의 웹 서비스와 스케줄러를 시작한다.
로컬 DB, 백업, 환경 설정이나 마이그레이션 적용 이력은 배포 대상이 아니다.
서버 DB의 django_migrations 이력을 기준으로 미적용된 Fitbit 스키마만 적용한다.
새 마이그레이션은 기존 행을 삭제하거나 재배정하지 않는다. 실제 교체를 최종 확인했을 때만
사용자와 사용 구간이 생성되고 지정 시각 이후 기록이 재배정된다.

운영 DB에는 이 작업 과정에서 마이그레이션이나 참여자 교체를 실행하지 않았다.
회귀 검증 대상: accounts.test_fitbit_replacement, accounts.test_participant_detail,
accounts.test_participant_sorting, survey.test_epds, survey.test_survey_regression.
