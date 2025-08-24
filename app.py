# app.py 또는 main.py

from flask import Flask, render_template
from datetime import date

app = Flask(__name__)

# 이 클래스는 데이터베이스 모델을 시뮬레이션합니다.
# 실제 프로젝트에서는 SQLAlchemy 같은 ORM을 사용하여 정의됩니다.
class Assets:
    def __init__(self, category, item, amount, notes, date_str):
        self.category = category
        self.item = item
        self.amount = amount
        self.notes = notes
        self.date = date_str

# 여기서는 더미(가짜) 데이터를 생성합니다.
# 실제 프로젝트에서는 데이터베이스에서 데이터를 쿼리해야 합니다.
mock_assets_data = [
    Assets('부동산', '아파트', 500000000, '아파트 매입', '2023-01-15'),
    Assets('금융자산', '주식', 12000000, '기술주 투자', '2023-02-20'),
    Assets('예금', '정기예금', 30000000, '생활비 예비', '2023-03-05'),
    Assets('기타', '자동차', 25000000, '중고차 구입', '2023-04-10'),
    Assets('부동산', '오피스텔', 150000000, '월세 수입용', '2023-05-18')
]

mock_house_data = [
    {'date': date(2023, 1, 31), 'maintenance_cost': 200000, 'utility_bill': 150000, 'memo': '1월 관리비 및 공과금'},
    {'date': date(2023, 2, 28), 'maintenance_cost': 195000, 'utility_bill': 140000, 'memo': '2월 관리비 및 공과금'},
]

# Flask 라우트 정의
@app.route('/')
def dashboard():
    # ----------------------------------------------------
    # 여기에서 오류가 발생했던 부분을 수정합니다.
    # Assets 객체를 tojson 필터가 처리할 수 있는 딕셔너리 리스트로 변환합니다.
    # ----------------------------------------------------
    assets_list_for_json = []
    for asset in mock_assets_data:
        assets_list_for_json.append({
            'date': asset.date,  # 날짜를 문자열로 변환
            'category': asset.category,
            'item': asset.item,
            'amount': asset.amount,
            'notes': asset.notes
        })

    # 카테고리별 자산 합계 계산 (원형 그래프용)
    category_totals = {}
    for asset in assets_list_for_json:
        category = asset['category']
        amount = asset['amount']
        category_totals[category] = category_totals.get(category, 0) + amount

    category_json_data = [{'category': cat, 'value': val} for cat, val in category_totals.items()]

    # HTML 템플릿 렌더링
    return render_template(
        'dashboard.html',
        assets_data=assets_list_for_json,
        house_data=mock_house_data,
        category_json=category_json_data
    )

if __name__ == '__main__':
    app.run(debug=True)
