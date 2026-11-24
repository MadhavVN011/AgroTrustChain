FROM python:3.11-slim-bookworm AS base

# Microsoft ODBC Driver 18 for SQL Server (pyodbc needs a system driver).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg ca-certificates unixodbc \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list -o /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn==23.0.0

COPY AgricultureFoodSupplyChain/AgricultureFoodSupplyChain/src/ .

RUN useradd --create-home --uid 1000 app

# `docker compose run --rm tests` runs the Python test suite in this stage.
FROM base AS test
RUN pip install --no-cache-dir pytest==8.3.4
COPY AgricultureFoodSupplyChain/AgricultureFoodSupplyChain/tests/ ./tests/
USER app
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]

FROM base AS app
USER app
EXPOSE 5000
# Hash any plain-text passwords left in the database, then serve. One worker
# so a missing FLASK_SECRET_KEY (random per process) still gives every request
# the same key; threads handle concurrency.
CMD ["sh", "-c", "python upgrade_passwords.py && exec gunicorn --bind 0.0.0.0:5000 --workers 1 --threads 8 --timeout 120 --access-logfile - AgricultureFoodSupplyChainV1Server:app"]
