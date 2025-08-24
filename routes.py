# routes.py
from flask import Blueprint, render_template, request, redirect, url_for
from database import get_db_connection

# Blueprint 생성 (메인 라우팅 그룹)
bp = Blueprint('main', __name__)

@bp.route('/')
def dashboard():
    conn = get_db_connection()
    assets = conn.execute('SELECT * FROM assets ORDER BY date DESC').fetchall()
    house_data = conn.execute('SELECT * FROM house_data ORDER BY date DESC').fetchall()
    conn.close()
    
    # 여기서 데이터 시각화 로직을 추가
    # ...
    
    return render_template('dashboard.html', assets_data=assets, house_data=house_data)

@bp.route('/add_asset', methods=['GET', 'POST'])
def add_asset():
    if request.method == 'POST':
        date = request.form['date']
        bank_balance = request.form.get('bank_balance', 0)
        investment_stock = request.form.get('investment_stock', 0)
        liabilities_loan = request.form.get('liabilities_loan', 0)
        notes = request.form['notes']
        
        conn = get_db_connection()
        conn.execute('INSERT INTO assets (date, bank_balance, investment_stock, liabilities_loan, notes) VALUES (?, ?, ?, ?, ?)',
                     (date, bank_balance, investment_stock, liabilities_loan, notes))
        conn.commit()
        conn.close()
        return redirect(url_for('main.dashboard'))
    return render_template('add_asset.html')

# 주택 관리 데이터 입력 라우트도 추가
@bp.route('/add_house', methods=['GET', 'POST'])
def add_house():
    if request.method == 'POST':
        date = request.form['date']
        maintenance_cost = request.form.get('maintenance_cost', 0)
        utility_bill = request.form.get('utility_bill', 0)
        memo = request.form['memo']
        
        conn = get_db_connection()
        conn.execute('INSERT INTO house_data (date, maintenance_cost, utility_bill, memo) VALUES (?, ?, ?, ?)',
                     (date, maintenance_cost, utility_bill, memo))
        conn.commit()
        conn.close()
        return redirect(url_for('main.dashboard'))
    return render_template('add_house.html')