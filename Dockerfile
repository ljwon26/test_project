# Python 공식 이미지를 기반으로 사용
FROM python:3.9-slim

# 작업 디렉토리 설정
WORKDIR /app

# 종속성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 5000번 포트 노출
EXPOSE 5000

# 애플리케이션 실행
CMD ["python", "app.py"]