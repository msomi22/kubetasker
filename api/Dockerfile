FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_NAME=KubeTasker \
    APP_MODE=learning \
    TASK_MODE=learning \
    LOG_LEVEL=info \
    ENABLE_SAMPLE_TASKS=true \
    WELCOME_MESSAGE="Welcome to KubeTasker" \
    CONFIG_FILE_PATH=/etc/kubetasker/app-config.yaml \
    APP_VERSION=0.2.0

WORKDIR /app

RUN addgroup --system kubetasker && adduser --system --ingroup kubetasker --uid 10001 kubetasker

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /data /etc/kubetasker/config /etc/kubetasker/secret \
    && chown -R kubetasker:kubetasker /app /data /etc/kubetasker

USER 10001

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
