FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# The runner executes LLM-generated code through pytest, so don't run as root.
RUN useradd --create-home appuser && mkdir -p results && chown -R appuser /app
USER appuser

# Cloud Run sets PORT (8080 by default).
CMD streamlit run app.py --server.port=${PORT:-8080} --server.address=0.0.0.0 --server.headless=true
