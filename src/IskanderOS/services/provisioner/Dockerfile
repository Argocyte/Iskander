FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r provisioner && useradd -r -g provisioner provisioner

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./provisioner/

RUN chown -R provisioner:provisioner /app

USER provisioner

ENV PYTHONPATH=/app

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import httpx; httpx.get('http://localhost:3001/health').raise_for_status()"

CMD ["uvicorn", "provisioner.main:app", "--host", "0.0.0.0", "--port", "3001"]
