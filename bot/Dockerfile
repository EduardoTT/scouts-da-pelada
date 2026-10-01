FROM python:3.13-slim

# git e ssh para clonar e publicar; tzdata para o fuso de Brasília;
# fontes que o build.py usa nas imagens de preview, como no deploy.yml.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git openssh-client tzdata fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /usr/local/bin/uv

ENV TZ=America/Sao_Paulo \
    VOLUME_DIR=/volume \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY . .

CMD ["uv", "run", "--frozen", "--no-sync", "python", "main.py"]
