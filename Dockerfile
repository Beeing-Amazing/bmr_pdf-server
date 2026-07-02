FROM python:3.13-slim

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
CMD ["uv", "run", "gunicorn", "server:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8853", "-w", "2"]
