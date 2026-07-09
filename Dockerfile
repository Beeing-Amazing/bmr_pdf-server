FROM python:3.13-slim

# ---
# SYSTEM DEPENDENCIES FOR WEASYPRINT
# ---
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libglib2.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# ---
# SETUP PYTHON
# ---
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# ---
# SETUP APP
# ---
WORKDIR /src

COPY ./pyproject.toml .
COPY ./uv.lock .
RUN uv sync --frozen

# ---
# RUN
# ---
COPY . ./
EXPOSE 8853

# RUN uv run fastapi run server.py --port 8853
CMD ["uv", "run", "gunicorn", "main:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8853", "-w", "2"]
