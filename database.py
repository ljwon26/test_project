# database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# SQLite 연결 URL을 정의합니다.
# 데이터베이스 파일은 현재 디렉터리에 'sql_app.db'라는 이름으로 생성됩니다.
SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"

# SQLite는 기본적으로 다중 스레드 환경에서 안전하지 않기 때문에
# check_same_thread=False 옵션을 추가합니다.
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()