from fastapi import FastAPI, Depends, Form, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Date, REAL, Float, func
import aiosmtplib
from email.mime.text import MIMEText
from pydantic import BaseModel
from datetime import date, timedelta, datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from urllib.parse import urlencode
import json
# 'database.py' 파일에서 필요한 객체들을 가져옵니다.
from database import SessionLocal, Base, engine, get_db

app = FastAPI()

# 정적 파일을 서빙하기 위한 설정입니다.
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

scheduler = AsyncIOScheduler()
scheduler.start()

# --- Pydantic 모델: 데이터 유효성 검사를 위한 클래스 ---
# Pydantic 모델은 클라이언트에서 전송되는 JSON 데이터의 형식을 정의합니다.
class TaskCreate(BaseModel):
    item_name: str
    model_name: str | None = None
    due_date: date
    email: str

class AssetCreate(BaseModel):
    date: date
    category: str
    item: str
    amount: float # 금액 필드 추가
    notes: str | None = None

class HouseDataCreate(BaseModel):
    date: date
    maintenance_cost: float | None = None
    utility_bill: float | None = None
    memo: str | None = None

class ExpenseCreate(BaseModel):
    date: date
    expense_type: str
    category: str
    item: str
    amount: float
    notes: str | None = None

# SQLAlchemy DB 모델: 데이터베이스 테이블과 매핑되는 클래스
# 이 클래스들은 데이터베이스의 테이블 구조를 정의합니다.
class Income(Base):
    __tablename__ = 'incomes'
    id = Column(Integer, primary_key=True, index=True)
    income_type = Column(String)
    amount = Column(Float)

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    item_name = Column(String(100), nullable=False)
    model_name = Column(String(100))
    due_date = Column(Date, nullable=False)
    email = Column(String(100), nullable=False)

class Assets(Base):
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False) # unique 속성 제거
    category = Column(String(50), nullable=False)
    item = Column(String(255), nullable=False)
    amount = Column(REAL, nullable=False) # 금액 필드 추가
    # `String` 타입에 길이를 추가합니다.
    notes = Column(String(255))

class HouseData(Base):
    __tablename__ = "house_data"
    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False)
    maintenance_cost = Column(REAL)
    utility_bill = Column(REAL)
    # `String` 타입에 길이를 추가합니다.
    memo = Column(String(255))

# 가계 지출 관리를 위한 새로운 Expense 모델을 추가합니다.
class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    expense_type = Column(String(50), nullable=False) # 고정적 or 변동적
    category = Column(String(100), nullable=False)
    item = Column(String(255), nullable=False)
    amount = Column(REAL, nullable=False)
    notes = Column(String(255))

# 데이터베이스에 모든 테이블을 생성합니다.
Base.metadata.create_all(bind=engine)

# --- 이메일 전송 설정 및 비동기 함수 ---
EMAIL_ADDRESS = "ljwon26@gmail.com"
EMAIL_PASSWORD = "qxxq unfr sfcg eoep"

async def send_email(to_email: str, subject: str, body: str):
    msg = MIMEText(body, _subtype='html')
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email

    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587

    try:
        async with aiosmtplib.SMTP(hostname=SMTP_SERVER, port=SMTP_PORT, start_tls=True) as server:
            await server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            await server.send_message(msg)
            print(f"이메일 전송 성공: {subject} to {to_email}")
    except Exception as e:
        print(f"이메일 전송 실패: {e}")

# --- 라우트 핸들러: API 엔드포인트 ---
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    # Assets 객체를 딕셔너리로 변환
    assets_data_db = db.query(Assets).order_by(Assets.date.desc()).all()
    assets_data_list = []
    for asset in assets_data_db:
        assets_data_list.append({
            'id': asset.id,
            'date': asset.date.isoformat(),
            'category': asset.category,
            'item': asset.item,
            'amount': asset.amount,
            'notes': asset.notes
        })
    
    # Task 객체를 딕셔너리로 변환하여 대시보드에 표시
    tasks_data_db = db.query(Task).order_by(Task.due_date.asc()).all()
    tasks_data_list = []
    for task in tasks_data_db:
        tasks_data_list.append({
            'item_name': task.item_name,
            'model_name': task.model_name,
            'due_date': task.due_date.isoformat(),
            'email': task.email
        })

    # 자산 카테고리별 비중 데이터 계산 (원형 그래프용)
    category_totals = {}
    for asset in assets_data_db:
        # 자산만 합산 (부채 제외)
        if "대출" not in asset.category and "부채" not in asset.category:
            if asset.category in category_totals:
                category_totals[asset.category] += asset.amount
            else:
                category_totals[asset.category] = asset.amount
    
    category_data = [{"category": k, "value": v} for k, v in category_totals.items()]

    # 지출 데이터를 딕셔너리로 변환하여 대시보드에 표시
    expenses_data_db = db.query(Expense).order_by(Expense.date.desc()).limit(10).all()
    expenses_data_list = []
    for expense in expenses_data_db:
        expenses_data_list.append({
            'id': expense.id,
            'date': expense.date.isoformat(),
            'expense_type': expense.expense_type,
            'category': expense.category,
            'item': expense.item,
            'amount': expense.amount,
            'notes': expense.notes
        })

    # 수입 데이터를 딕셔너리로 변환하여 대시보드에 표시
    incomes_data_db = db.query(Income).order_by(Income.id.desc()).limit(10).all()
    incomes_data_list = []
    for income in incomes_data_db:
        incomes_data_list.append({
            'id': income.id,
            'income_type': income.income_type,
            'amount': income.amount
        })

    # 이번 달 지출 데이터 집계 (그래프용)
    today = date.today()
    start_of_month = today.replace(day=1)
    monthly_expenses = db.query(Expense).filter(Expense.date >= start_of_month).all()
    
    expense_category_totals = {}
    for expense in monthly_expenses:
        if expense.category in expense_category_totals:
            expense_category_totals[expense.category] += expense.amount
        else:
            expense_category_totals[expense.category] = expense.amount
            
    expense_category_data = [{"category": k, "value": v} for k, v in expense_category_totals.items()]

    # 총 수입과 총 지출 계산
    total_income = db.query(func.sum(Income.amount)).scalar() or 0
    total_expense = db.query(func.sum(Expense.amount)).scalar() or 0

    # JSON.parse를 사용하지 않고 Jinja2의 tojson 필터가 바로 처리할 수 있도록 딕셔너리/리스트 형태로 전달
    category_json = category_data
    expense_category_json = expense_category_data

    # `today` 변수를 템플릿에 전달합니다.
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "assets_data": assets_data_list, # 변환된 리스트 전달
        "tasks_data": tasks_data_list,  # 변환된 알림 목록 전달
        "expenses_data": expenses_data_list, # 최근 지출 데이터 전달
        "incomes_data": incomes_data_list, # 최근 수입 데이터 전달
        "category_json": category_json,
        "expense_category_json": expense_category_json,
        "total_income": total_income,
        "total_expense": total_expense,
        "today": today.isoformat()
    })

@app.get("/add_asset", response_class=HTMLResponse)
def add_asset_form(request: Request):
    # `today` 변수를 템플릿에 전달합니다.
    return templates.TemplateResponse("add_asset.html", {"request": request, "today": date.today().isoformat()})

@app.post("/add_asset", response_class=RedirectResponse)
def create_asset(
    date: date = Form(...),
    category: str = Form(...),
    item: str = Form(...),
    amount: float = Form(...), # 금액 폼 데이터 추가
    notes: str | None = Form(None),
    db: Session = Depends(get_db)
):
    new_asset = Assets(
        date=date,
        category=category,
        item=item,
        amount=amount,
        notes=notes
    )
    db.add(new_asset)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

# 수정 라우트 추가
@app.get("/edit_asset/{asset_id}", response_class=HTMLResponse)
def edit_asset_form(request: Request, asset_id: int, db: Session = Depends(get_db)):
    asset_data = db.query(Assets).filter(Assets.id == asset_id).first()
    if not asset_data:
        raise HTTPException(status_code=404, detail="Asset not found")

    # 금액이 .0으로 표시되지 않도록 수정
    # float이 정수인지 확인하고, 정수이면 정수로 변환
    if asset_data.amount and asset_data.amount.is_integer():
        asset_data.amount = int(asset_data.amount)
    
    return templates.TemplateResponse("edit_asset.html", {
        "request": request,
        "asset_data": asset_data,
        "today": date.today().isoformat()
    })

@app.post("/edit_asset/{asset_id}", response_class=RedirectResponse)
def update_asset(
    asset_id: int,
    date: date = Form(...),
    category: str = Form(...),
    item: str = Form(...),
    amount: float = Form(...),
    notes: str | None = Form(None),
    db: Session = Depends(get_db)
):
    asset = db.query(Assets).filter(Assets.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    asset.date = date
    asset.category = category
    asset.item = item
    asset.amount = amount
    asset.notes = notes
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/delete_asset", response_class=RedirectResponse)
def delete_asset(asset_id: int = Form(...), db: Session = Depends(get_db)):
    asset = db.query(Assets).filter(Assets.id == asset_id).first()
    if asset:
        db.delete(asset)
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.get("/add_house", response_class=HTMLResponse)
def add_house_form(request: Request):
    # `today` 변수를 템플릿에 전달합니다.
    return templates.TemplateResponse("add_house.html", {"request": request, "today": date.today().isoformat()})

@app.post("/add_house", response_class=RedirectResponse)
def create_house_data(
    date: date = Form(...),
    maintenance_cost: float | None = Form(None),
    utility_bill: float | None = Form(None),
    memo: str | None = Form(None),
    db: Session = Depends(get_db)
):
    # Pydantic 모델을 사용하지 않고 Form()을 통해 데이터를 직접 받습니다.
    # 해당 날짜에 이미 레코드가 있는지 확인합니다.
    existing_house_data = db.query(HouseData).filter(HouseData.date == date).first()

    # 이미 레코드가 존재하면 업데이트하고, 없으면 새로 추가합니다.
    if existing_house_data:
        existing_house_data.maintenance_cost = maintenance_cost
        existing_house_data.utility_bill = utility_bill
        existing_house_data.memo = memo
    else:
        new_house_data = HouseData(
            date=date,
            maintenance_cost=maintenance_cost,
            utility_bill=utility_bill,
            memo=memo
        )
        db.add(new_house_data)
        
    db.commit()
    return RedirectResponse(url="/", status_code=303)
    
@app.get("/notifications", response_class=HTMLResponse)
def read_tasks(request: Request, db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    # `today` 변수를 템플릿에 전달합니다.
    return templates.TemplateResponse("add_task.html", {"request": request, "tasks": tasks, "today": date.today().isoformat()})

@app.get("/add_notification", response_class=HTMLResponse)
def add_notification_form(request: Request):
    # `today` 변수를 템플릿에 전달합니다.
    return templates.TemplateResponse("add_task.html", {"request": request, "today": date.today().isoformat()})
# 알림 삭제
@app.post("/delete_notification/{task_id}", response_class=RedirectResponse)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    """
    지정된 ID의 알림을 데이터베이스에서 삭제합니다.
    """
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if db_task:
        db.delete(db_task)
        db.commit()
    # 알림 목록 페이지로 리다이렉트합니다.
    return RedirectResponse(url="/notifications", status_code=303)

# 알림 수정 폼 로드
@app.get("/edit_notification/{task_id}", response_class=HTMLResponse)
def edit_notification_form(request: Request, task_id: int, db: Session = Depends(get_db)):
    """
    지정된 ID의 알림 데이터를 수정 폼에 로드합니다.
    """
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return templates.TemplateResponse("add_task.html", {
        "request": request,
        "task": task,
        "today": date.today().isoformat()
    })

# 알림 수정 처리
@app.post("/edit_notification/{task_id}", response_class=RedirectResponse)
def edit_notification_post(
    task_id: int,
    item_name: str = Form(...),
    model_name: str | None = Form(None),
    due_date: date = Form(...),
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    폼 데이터를 받아 지정된 ID의 알림을 업데이트합니다.
    """
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if db_task:
        db_task.item_name = item_name
        db_task.model_name = model_name
        db_task.due_date = due_date
        db_task.email = email
        db.commit()
        db.refresh(db_task)
    return RedirectResponse(url="/notifications", status_code=303)

@app.post("/add_notification", response_class=RedirectResponse)
def add_task_form_post(
    item_name: str = Form(...),
    model_name: str | None = Form(None),
    due_date: date = Form(...),
    email: str = Form(...),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):

    db_task = Task(
        item_name=item_name,
        model_name=model_name,
        due_date=due_date,
        email=email
    )
    db.add(db_task)
    db.commit()

    
    subject_initial = f"[J&D 하우스 관리] 새 일정 등록 완료: {item_name}"
    html_body_initial = f"""
    <div style="font-family: Arial, sans-serif; background-color: #f4f7f9; padding: 20px; text-align: center;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            <h1 style="color: #1e3a8a; margin-top: 0; font-size: 28px;">🏠 하우스 관리 알림</h1>
            <p style="font-size: 16px; color: #555;">안녕하세요, '{item_name}' 일정이 성공적으로 등록되었습니다.</p>
            <hr style="border: 0; height: 1px; background-color: #eee; margin: 20px 0;">
            <table style="width: 100%; text-align: left; border-collapse: collapse;">
                <tr>
                    <td style="padding: 10px; font-weight: bold; color: #1e3a8a;">일정 항목</td>
                    <td style="padding: 10px; color: #333;">{item_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; font-weight: bold; color: #1e3a8a;">세부 모델</td>
                    <td style="padding: 10px; color: #333;">{model_name if model_name else '없음'}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; font-weight: bold; color: #1e3a8a;">마감일</td>
                    <td style="padding: 10px; color: #ef4444; font-weight: bold;">{due_date}</td>
                </tr>
            </table>
            <p style="font-size: 14px; color: #888; margin-top: 30px;">본 메일은 자동 발송된 메일입니다. 회신하지 마세요.</p>
        </div>
    </div>
    """
    background_tasks.add_task(send_email, to_email=email, subject=subject_initial, body=html_body_initial)

    subject_due = f"[J&D 하우스 관리] 마감일 알림: {item_name}"
    html_body_due = f"""
    <div style="font-family: Arial, sans-serif; background-color: #f4f7f9; padding: 20px; text-align: center;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
            <h1 style="color: #ef4444; margin-top: 0; font-size: 28px;"> 마감일이 얼마 남지 않았습니다!</h1>
            <p style="font-size: 16px; color: #555;">'{item_name}'의 마감일이 오늘입니다.</p>
            <hr style="border: 0; height: 1px; background-color: #eee; margin: 20px 0;">
            <table style="width: 100%; text-align: left; border-collapse: collapse;">
                <tr>
                    <td style="padding: 10px; font-weight: bold; color: #1e3a8a;">일정 항목</td>
                    <td style="padding: 10px; color: #333;">{item_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; font-weight: bold; color: #1e3a8a;">세부 모델</td>
                    <td style="padding: 10px; color: #333;">{model_name if model_name else '없음'}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; font-weight: bold; color: #1e3a8a;">마감일</td>
                    <td style="padding: 10px; color: #ef4444; font-weight: bold;">{due_date}</td>
                </tr>
            </table>
            <p style="font-size: 14px; color: #888; margin-top: 30px;">일정 관리 페이지를 방문하여 해당 일정을 완료로 표시해주세요.</p>
        </div>
    </div>
    """

    today = date.today()
    if due_date >= today:
        # 마감일 당일 오전 9시에 알림을 보냅니다.
        run_date_due = datetime.combine(due_date, datetime.min.time()).replace(hour=9, minute=0)
        scheduler.add_job(
            send_email,
            'date',
            run_date=run_date_due,
            args=[email, subject_due, html_body_due]
        )
    
        # 마감일 하루 전 오전 9시에 알림을 보냅니다.
        due_date_minus_one = due_date - timedelta(days=1)
        run_date_before = datetime.combine(due_date_minus_one, datetime.min.time()).replace(hour=9, minute=0)
        scheduler.add_job(
            send_email,
            'date',
            run_date=run_date_before,
            args=[email, subject_due, html_body_due]
        )

    # 이전 코드에서는 여기서 '/notifications'로 리디렉션하여 템플릿이 변경되었습니다.
    # 이제 '/add_notification' 페이지로 돌아가도록 수정했습니다.
    query_params = urlencode({"message": "알림이 성공적으로 등록되었습니다!"})
    return RedirectResponse(url=f"/add_notification?{query_params}", status_code=303)

@app.post("/delete_task", response_class=RedirectResponse)
def delete_task(task_id: int = Form(...), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        db.delete(task)
        db.commit()
    return RedirectResponse(url="/notifications", status_code=303)

# 새로운 지출 관리 라우트
@app.get("/expenses", response_class=HTMLResponse)
def get_expenses(request: Request, db: Session = Depends(get_db)):
    expenses = db.query(Expense).order_by(Expense.date.desc()).all()
    incomes = db.query(Income).order_by(Income.id.desc()).all() # 수입 데이터 가져오기
    
    # Jinja2 템플릿에 전달하기 전에 금액을 정수형으로 변환합니다.
    # 이렇게 하면 템플릿에서 '| int' 필터가 필요하지 않습니다.
    for expense in expenses:
        if expense.amount and expense.amount.is_integer():
            expense.amount = int(expense.amount)
    
    for income in incomes:
        if income.amount and income.amount.is_integer():
            income.amount = int(income.amount)

    # `today` 변수를 템플릿에 전달합니다.
    return templates.TemplateResponse("expenses.html", {
        "request": request, 
        "expenses": expenses, 
        "incomes": incomes, # 수입 데이터도 함께 전달
        "today": date.today().isoformat()
    })

@app.post("/add_expense", response_class=RedirectResponse)
def add_expense(
    expense_type: str = Form(...),
    category: str = Form(...),
    item: str = Form(...),
    amount: float = Form(...),
    notes: str | None = Form(None),
    db: Session = Depends(get_db)
):
    # SQLAlchemy 모델에 새로운 지출 항목을 생성합니다.
    new_expense = Expense(
        date=date.today(), # 현재 날짜를 자동으로 추가
        expense_type=expense_type,
        category=category,
        item=item,
        amount=amount,
        notes=notes
    )
    db.add(new_expense)
    db.commit()
    return RedirectResponse(url="/expenses", status_code=303)

# 지출 항목 수정 페이지를 띄우기 위한 GET 라우트 추가
@app.get("/edit_expense/{expense_id}", response_class=HTMLResponse)
def edit_expense_form(request: Request, expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    return templates.TemplateResponse("edit_expense.html", {
        "request": request,
        "expense": expense,
        "today": date.today().isoformat()
    })

@app.post("/edit_expense/{expense_id}", response_class=RedirectResponse)
def update_expense(
    expense_id: int,
    date: date = Form(...),
    expense_type: str = Form(...),
    category: str = Form(...),
    item: str = Form(...),
    amount: float = Form(...),
    notes: str | None = Form(None),
    db: Session = Depends(get_db)
):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    expense.date = date
    expense.expense_type = expense_type
    expense.category = category
    expense.item = item
    expense.amount = amount
    expense.notes = notes
    db.commit()
    return RedirectResponse(url="/expenses", status_code=303)

@app.post("/delete_expense", response_class=RedirectResponse)
def delete_expense(expense_id: int = Form(...), db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if expense:
        db.delete(expense)
        db.commit()
    return RedirectResponse(url="/expenses", status_code=303)

# --- 수입 관련 라우트 추가 ---

@app.post("/add_income", response_class=RedirectResponse)
def add_income(
    income_type: str = Form(...),
    amount: float = Form(...),
    db: Session = Depends(get_db)
):
    new_income = Income(
        income_type=income_type,
        amount=amount
    )
    db.add(new_income)
    db.commit()
    return RedirectResponse(url="/expenses", status_code=303)

# 수입 항목 수정 페이지를 띄우기 위한 GET 라우트 추가
@app.get("/edit_income/{income_id}", response_class=HTMLResponse)
def edit_income_form(request: Request, income_id: int, db: Session = Depends(get_db)):
    income = db.query(Income).filter(Income.id == income_id).first()
    if not income:
        raise HTTPException(status_code=404, detail="Income not found")
        
    return templates.TemplateResponse("edit_income.html", {
        "request": request,
        "income": income
    })

@app.post("/edit_income/{income_id}", response_class=RedirectResponse)
def update_income(
    income_id: int,
    income_type: str = Form(...),
    amount: float = Form(...),
    db: Session = Depends(get_db)
):
    income = db.query(Income).filter(Income.id == income_id).first()
    if not income:
        raise HTTPException(status_code=404, detail="Income not found")

    income.income_type = income_type
    income.amount = amount
    db.commit()
    return RedirectResponse(url="/expenses", status_code=303)

@app.post("/delete_income", response_class=RedirectResponse)
def delete_income(income_id: int = Form(...), db: Session = Depends(get_db)):
    income = db.query(Income).filter(Income.id == income_id).first()
    if income:
        db.delete(income)
        db.commit()
    return RedirectResponse(url="/expenses", status_code=303)


if __name__ == "__main__":
    import uvicorn
    # 외부 접속을 허용하기 위해 `host`를 '0.0.0.0'으로 변경합니다.
    uvicorn.run(app, host="0.0.0.0", port=8000)
