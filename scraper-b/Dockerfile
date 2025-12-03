FROM python:3.12-slim
WORKDIR /app

# install deps
COPY scraper-b/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy shared + service code
COPY common/ ./common/
COPY scraper-b/ ./scraper-b/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
WORKDIR /app/scraper-b
CMD ["sh","-c","uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]