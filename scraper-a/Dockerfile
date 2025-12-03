FROM python:3.12-slim
WORKDIR /app

# install deps
COPY scraper-a/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy shared + service code
COPY common/ ./common/
COPY scraper-a/ ./scraper-a/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
WORKDIR /app/scraper-a
CMD ["sh","-c","uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
