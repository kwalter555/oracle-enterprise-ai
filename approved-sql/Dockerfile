FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    groupadd --gid 10001 sqlreview && useradd --uid 10001 --gid 10001 --no-create-home sqlreview && \
    mkdir /state && chown 10001:10001 /state && chmod 700 /state
COPY policy.py ledger.py database.py service.py check.py ./
USER 10001:10001
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/health', timeout=3).read()"
CMD ["uvicorn", "service:production_app", "--factory", "--host", "0.0.0.0", "--port", "8081", "--workers", "1", "--no-access-log"]
