import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# MySQL 연결을 위한 라이브러리(pymysql)를 임포트합니다.
# 이 라이브러리가 설치되지 않았다면, 'pip install pymysql' 명령어를 실행하세요.
import pymysql
pymysql.install_as_MySQLdb()

# 데이터베이스 연결 URL을 정의합니다.
# 사용자 이름, 비밀번호, 호스트, 포트, 데이터베이스 이름을 실제 환경에 맞게 수정해야 합니다.
# 형식: "mysql+pymysql://<user>:<password>@<host>:<port>/<db_name>"
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:nds1101@localhost:3306/my_house_manager"

# 데이터베이스 엔진을 생성합니다.
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True)

# 데이터베이스 세션을 생성하는 클래스입니다.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# SQLAlchemy 모델의 기본 클래스입니다.
Base = declarative_base()

# 의존성 주입을 위한 함수입니다.
# 요청이 들어올 때마다 새로운 DB 세션을 생성하고, 요청이 끝나면 세션을 닫습니다.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
