FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY problems/ ./problems/
COPY tests/ ./tests/

RUN pip install --no-cache-dir -e . && \
    python -c "import verifier_sandbox, problems.registry"

CMD ["python", "-m", "verifier_sandbox.cli", "demo"]
