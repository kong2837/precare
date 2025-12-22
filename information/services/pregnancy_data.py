# information/services/pregnancy_data.py
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

EXCEL_PATH = BASE_DIR / 'information' / 'services' / 'data' / '임신주수별 산모 및 태아 정보.xlsx'

# def load_pregnancy_data():
#     df = pd.read_excel(EXCEL_PATH)

#     data = {}
    
#     df = df.drop(df.columns[[0, 1]], axis=1)
    
#     for _, row in df.iterrows():
#         week = int(row['임신주수'])
#         data[week] = {
#             'baby': row['우리 아기는? (태아)'],
#             'mother': row['엄마는요? (산모)'],
#             'tip': row['주수별 관리 TIP & CHECK!'],
#         }
#     return data

import re

def load_pregnancy_data():
    # header=2는 엑셀의 3행을 실제 컬럼 이름으로 쓰겠다는 의미입니다.
    df = pd.read_excel(EXCEL_PATH, header=2)

    data = {}
    
    for _, row in df.iterrows():
        # '임신주수' 컬럼 값을 문자열로 변환
        week_str = str(row['임신주수'])
        
        # '1주', '2주' 처럼 '주'라는 글자가 포함된 경우만 처리
        if '주' in week_str:
            try:
                # "1주"에서 숫자 1만 추출하여 정수로 변환
                week_num = int(''.join(filter(str.isdigit, week_str)))
                
                data[week_num] = {
                    'baby': row['우리 아기는? (태아)'],
                    'mother': row['엄마는요? (산모)'],
                    'tip': row['주수별 관리 TIP & CHECK!'],
                }
            except ValueError:
                # 숫자로 변환할 수 없는 경우(예: '임신초기') 건너뜁니다.
                continue
                
    return data


PREGNANCY_DATA = load_pregnancy_data()
