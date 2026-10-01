FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /bin/uv
WORKDIR /srv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY main.py ./
COPY app ./app
RUN useradd -m appuser
USER appuser
ENV PATH="/srv/.venv/bin:$PATH"
CMD ["python", "main.py"]
