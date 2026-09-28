FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp XDG_CACHE_HOME=/tmp/.cache LITELLM_LOCAL_MODEL_COST_MAP=True DO_NOT_TRACK=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip check
COPY app.py .
USER 10001:10001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "4000", "--no-access-log", "--no-proxy-headers"]
