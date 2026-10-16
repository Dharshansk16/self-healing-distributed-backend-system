FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY target-cluster/common /app/common
COPY target-cluster/services/order-service/app.py /app/app.py

ENV PORT=8002
EXPOSE 8002

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]
