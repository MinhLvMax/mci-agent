FROM python:3.12-slim

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Cài thư viện trước để Docker cache lại, chỉ cài lại khi requirements thay đổi
COPY requirements.txt .
RUN #pip install -r requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY .streamlit ./.streamlit
COPY src ./src

# Lệnh chạy cụ thể (api hay ui) được khai báo trong docker-compose.yml
