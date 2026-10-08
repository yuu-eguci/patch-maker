FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir "pytest==8.4.2" "ruff==0.13.3"

COPY . .

CMD ["python", "PatchMaker.py"]
