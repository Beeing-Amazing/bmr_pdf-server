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
RUN uv sync --quiet --frozen

# ---
# RUN
# ---
COPY .env server.py ./
EXPOSE 8853

RUN uv run fastapi run server.py --port 8853
