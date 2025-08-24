# main.py

from fastapi import FastAPI, Depends, Form, Request, BackgroundTasks, HTTPException, status
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
import os # 환경 변수 사용을 위해 추가
from starlette.middleware.sessions import SessionMiddleware # 세션 미들웨어 추가

# 'database.py' 파일에서 필요한 객체들을 가져옵니다.
from database import SessionLocal, Base, engine, get_db

app = FastAPI()

# --- 세션 미들웨어 추가 ---
# !! 보안 경고: 아래 secret_key는 예시이며, 실제 운영 환경에서는
# 절대로 코드에 직접 작성하지 말고 환경 변수 등을 사용해 안전하게 관리해야 합니다.
# 터미널에서 'openssl rand -hex 32' 명령어로 강력한 키를 생성할 수 있습니다.
SECRET_KEY = os.getenv("SECRET_KEY", "a_very_secret_key_that_should_be_changed")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# --- 로그인에 사용할 비밀번호 설정 ---
# !! 이 또한 실제 운영 환경에서는 환경 변수로 관리하는 것이 안전합니다.
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "3152")


# 정적 파일을 서빙하기 위한 설정입니다.
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

scheduler = AsyncIOScheduler()
scheduler.start()

# --- Pydantic 모델: 데이터 유효성 검사를 위한 클래스 ---
class TaskCreate(BaseModel):
    item_name: str
    model_name: str | None = None
    due_date: date
    email: str

class AssetCreate(BaseModel):
    date: date
    category: str
    item: str
    amount: float
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
    date = Column(Date, nullable=False)
    category = Column(String(50), nullable=False)
    item = Column(String(255), nullable=False)
    amount = Column(REAL, nullable=False)
    notes = Column(String(255))

class HouseData(Base):
    __tablename__ = "house_data"
    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False)
    maintenance_cost = Column(REAL)
    utility_bill = Column(REAL)
    memo = Column(String(255))

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    expense_type = Column(String(50), nullable=False)
    category = Column(String(100), nullable=False)
    item = Column(String(255), nullable=False)
    amount = Column(REAL, nullable=False)
    notes = Column(String(255))

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

# --- 로그인/로그아웃 라우트 추가 ---

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, error: str | None = None):
    """로그인 폼을 보여주는 페이지입니다."""
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.post("/login", response_class=RedirectResponse)
async def login_post(request: Request, password: str = Form(...)):
    """로그인 요청을 처리합니다."""
    if password == LOGIN_PASSWORD:
        request.session['logged_in'] = True
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    else:
        return RedirectResponse(url="/login?error=1", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/logout", response_class=RedirectResponse)
async def logout(request: Request):
    """로그아웃을 처리하고 세션을 초기화합니다."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

# --- 로그인 상태 확인 의존성(Dependency) ---
async def verify_login(request: Request):
    """
    세션을 확인하여 로그인 상태가 아니면 로그인 페이지로 리디렉션하는 의존성 함수.
    """
    if not request.session.get('logged_in'):
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )

# --- 라우트 핸들러: API 엔드포인트 ---
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), _: bool = Depends(verify_login)):
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
        if "대출" not in asset.category and "부채" not in asset.category:
            if asset.category in category_totals:
                category_totals[asset.category] += asset.amount
            else:
                category_totals[asset.category] = asset.amount
    
    category_data = [{"category": k, "value": v} for k, v in category_totals.items()]

    # 지출 데이터를 딕셔너리로 변환
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

    # 수입 데이터를 딕셔너리로 변환
    incomes_data_db = db.query(Income).order_by(Income.id.desc()).limit(10).all()
    incomes_data_list = []
    for income in incomes_data_db:
        incomes_data_list.append({
            'id': income.id,
            'income_type': income.income_type,
            'amount': income.amount
        })

    # 이번 달 지출 데이터 집계
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

    category_json = category_data
    expense_category_json = expense_category_data

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "assets_data": assets_data_list,
        "tasks_data": tasks_data_list,
        "expenses_data": expenses_data_list,
        "incomes_data": incomes_data_list,
        "category_json": category_json,
        "expense_category_json": expense_category_json,
        "total_income": total_income,
        "total_expense": total_expense,
        "today": today.isoformat()
    })

@app.get("/add_asset", response_class=HTMLResponse)
def add_asset_form(request: Request, _: bool = Depends(verify_login)):
    return templates.TemplateResponse("add_asset.html", {"request": request, "today": date.today().isoformat()})

@app.post("/add_asset", response_class=RedirectResponse)
def create_asset(
    date: date = Form(...),
    category: str = Form(...),
    item: str = Form(...),
    amount: float = Form(...),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_login)
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

@app.get("/edit_asset/{asset_id}", response_class=HTMLResponse)
def edit_asset_form(request: Request, asset_id: int, db: Session = Depends(get_db), _: bool = Depends(verify_login)):
    asset_data = db.query(Assets).filter(Assets.id == asset_id).first()
    if not asset_data:
        raise HTTPException(status_code=404, detail="Asset not found")
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
    db: Session = Depends(get_db),
    _: bool = Depends(verify_login)
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
def delete_asset(asset_id: int = Form(...), db: Session = Depends(get_db), _: bool = Depends(verify_login)):
    asset = db.query(Assets).filter(Assets.id == asset_id).first()
    if asset:
        db.delete(asset)
        db.commit()
    return RedirectResponse(url="/", status_code=303)

# ... (이하 모든 라우트 함수에 _: bool = Depends(verify_login) 를 추가해주세요) ...

# 예시:
@app.get("/expenses", response_class=HTMLResponse)
def get_expenses(request: Request, db: Session = Depends(get_db), _: bool = Depends(verify_login)):
    expenses = db.query(Expense).order_by(Expense.date.desc()).all()
    incomes = db.query(Income).order_by(Income.id.desc()).all()
    
    for expense in expenses:
        if expense.amount and expense.amount.is_integer():
            expense.amount = int(expense.amount)
    
    for income in incomes:
        if income.amount and income.amount.is_integer():
            income.amount = int(income.amount)

    return templates.TemplateResponse("expenses.html", {
        "request": request, 
        "expenses": expenses, 
        "incomes": incomes,
        "today": date.today().isoformat()
    })

# ... (add_expense, edit_income 등 다른 모든 POST, GET 라우트에도 동일하게 적용)


# --- uvicorn 실행 부분 ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)