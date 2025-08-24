from fastapi import FastAPI, Depends, Form, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal, Base, engine
from sqlalchemy import Column, Integer, String, Date
import aiosmtplib
from email.mime.text import MIMEText
from pydantic import BaseModel
from datetime import date, timedelta, datetime # 📢 datetime도 추가로 임포트
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# FastAPI 앱 인스턴스 생성
app = FastAPI()

templates = Jinja2Templates(directory="templates")

# APScheduler 인스턴스 생성 및 시작
scheduler = AsyncIOScheduler()
scheduler.start()

# --- Pydantic 모델 ---
class TaskCreate(BaseModel):
    item_name: str
    model_name: str | None = None
    due_date: date
    email: str

# --- DB 모델 ---
class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    item_name = Column(String(100), nullable=False)
    model_name = Column(String(100))
    due_date = Column(Date, nullable=False)
    email = Column(String(100), nullable=False)

Base.metadata.create_all(bind=engine)

# --- DB 세션 의존성 주입 함수 ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

# --- 라우트 핸들러 ---
@app.get("/", response_class=HTMLResponse)
def read_tasks(request: Request, db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    return templates.TemplateResponse("task_list.html", {"request": request, "tasks": tasks})

@app.get("/add", response_class=HTMLResponse)
def add_task_form(request: Request):
    return templates.TemplateResponse("add_task.html", {"request": request})

@app.post("/add_form")
def add_task_form_post(
    task: TaskCreate,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    # Pydantic 모델의 데이터를 사용하여 DB 객체 생성
    db_task = Task(
        item_name=task.item_name,
        model_name=task.model_name,
        due_date=task.due_date,
        email=task.email
    )
    db.add(db_task)
    db.commit()
    
    # 1. 등록 즉시 알림 메일 전송
    subject_initial = f"[J&D 하우스 관리] 새 일정 등록 완료: {task.item_name}"
    html_body_initial = f"""
    <div style="font-family: Arial, sans-serif; background-color: #f4f7f9; padding: 20px; text-align: center;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            <h1 style="color: #1e3a8a; margin-top: 0; font-size: 28px;">🏠 하우스 관리 알림</h1>
            <p style="font-size: 16px; color: #555;">안녕하세요, '{task.item_name}' 일정이 성공적으로 등록되었습니다.</p>
            <hr style="border: 0; height: 1px; background-color: #eee; margin: 20px 0;">
            <table style="width: 100%; text-align: left; border-collapse: collapse;">
                <tr>
                    <td style="padding: 10px; font-weight: bold; color: #1e3a8a;">일정 항목</td>
                    <td style="padding: 10px; color: #333;">{task.item_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; font-weight: bold; color: #1e3a8a;">세부 모델</td>
                    <td style="padding: 10px; color: #333;">{task.model_name if task.model_name else '없음'}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; font-weight: bold; color: #1e3a8a;">마감일</td>
                    <td style="padding: 10px; color: #ef4444; font-weight: bold;">{task.due_date}</td>
                </tr>
            </table>
            <p style="font-size: 14px; color: #888; margin-top: 30px;">본 메일은 자동 발송된 메일입니다. 회신하지 마세요.</p>
        </div>
    </div>
    """
    background_tasks.add_task(send_email, to_email=task.email, subject=subject_initial, body=html_body_initial)

    # 마감일 알림용 이메일 내용
    subject_due = f"[J&D 하우스 관리] 마감일 알림: {task.item_name}"
    html_body_due = f"""
    <div style="font-family: Arial, sans-serif; background-color: #f4f7f9; padding: 20px; text-align: center;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
            <h1 style="color: #ef4444; margin-top: 0; font-size: 28px;">🚨 마감일이 얼마 남지 않았습니다!</h1>
            <p style="font-size: 16px; color: #555;">'{task.item_name}'의 마감일이 오늘입니다.</p>
            <hr style="border: 0; height: 1px; background-color: #eee; margin: 20px 0;">
            <table style="width: 100%; text-align: left; border-collapse: collapse;">
                <tr>
                    <td style="padding: 10px; font-weight: bold; color: #1e3a8a;">일정 항목</td>
                    <td style="padding: 10px; color: #333;">{task.item_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; font-weight: bold; color: #1e3a8a;">세부 모델</td>
                    <td style="padding: 10px; color: #333;">{task.model_name if task.model_name else '없음'}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; font-weight: bold; color: #1e3a8a;">마감일</td>
                    <td style="padding: 10px; color: #ef4444; font-weight: bold;">{task.due_date}</td>
                </tr>
            </table>
            <p style="font-size: 14px; color: #888; margin-top: 30px;">일정 관리 페이지를 방문하여 해당 일정을 완료로 표시해주세요.</p>
        </div>
    </div>
    """

    # 오늘 날짜
    today = date.today()
    # 📢 현재 시간의 시와 분을 가져옴
    now = datetime.now()

    # 마감일이 오늘이거나 미래인 경우에만 스케줄링
    if task.due_date >= today:
        # 2. 마감일 당일 알림 예약 (현재 시간의 시와 분으로 설정)
        # 📢 .replace(hour=9, minute=0) 부분을 .replace(hour=now.hour, minute=now.minute + 1) 로 변경
        # 이렇게 하면 등록 후 다음 분에 바로 알림이 옵니다.
        # 주의: 60분 이상이 될 경우 오류가 발생할 수 있으므로, 테스트용으로만 사용하세요.
        
        #run_date_due = datetime.combine(task.due_date, datetime.min.time()).replace(hour=now.hour, minute=now.minute + 1, second=0)
        run_date_due = datetime.combine(task.due_date, datetime.min.time()).replace(hour=9, minute=0)
        scheduler.add_job(
            send_email,
            'date',
            run_date=run_date_due,
            args=[task.email, subject_due, html_body_due]
        )

        # 3. 마감일 하루 전 알림 예약 (현재 시간의 시와 분으로 설정)
        due_date_minus_one = task.due_date - timedelta(days=1)
        run_date_before = datetime.combine(due_date_minus_one, datetime.min.time()).replace(hour=now.hour, minute=now.minute + 1, second=0)
        scheduler.add_job(
            send_email,
            'date',
            run_date=run_date_before,
            args=[task.email, subject_due, html_body_due]
        )
    
    return {"message": f"{task.item_name} 일정이 등록되었습니다!<br>이메일 알림이 전송됩니다."}

@app.post("/delete_task")
def delete_task(task_id: int = Form(...), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        db.delete(task)
        db.commit()
    return RedirectResponse(url="/", status_code=303)