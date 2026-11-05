FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN pip install --no-cache-dir 'torch>=2.6,<3' --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt backend/requirements-tracking.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt -r backend/requirements-tracking.txt
COPY backend ./backend
COPY pricing ./pricing
RUN useradd --create-home researcher && mkdir -p /data /mlflow && chown researcher:researcher /data /mlflow
USER researcher
ENV DATA_DIR=/data
EXPOSE 8000
CMD ["python","-m","uvicorn","backend.app.main:app","--host","0.0.0.0","--port","8000","--workers","1","--proxy-headers","--forwarded-allow-ips","127.0.0.1"]
