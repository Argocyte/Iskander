FROM python:3.12-slim

WORKDIR /app

# Install deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py schema.sql ./

# Non-root user
RUN useradd -r -u 1000 steward
USER steward

EXPOSE 4000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4000"]
