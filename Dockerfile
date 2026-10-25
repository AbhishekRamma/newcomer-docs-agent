FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/hf PIP_NO_CACHE_DIR=1
WORKDIR /app

# CPU-only torch keeps the image far smaller than the default CUDA build.
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.*" \
 && pip install uv

COPY pyproject.toml ./
COPY src ./src
RUN uv pip install --system ".[embed]"

# Bake the embedding model into the image so the API does not download it at runtime.
RUN python -c "from sentence_transformers import SentenceTransformer as S; S('BAAI/bge-small-en-v1.5')"

COPY data/sources.json data/sources.json
COPY ci ./ci

EXPOSE 8000
# Apply SQL migrations (question_history), build the c500 index (uses data/local/ if mounted:
# cached pages and embeddings), then serve.
CMD ["sh", "-c", "python -m src.migrate && python -m src.ingest --sizes 500 && uvicorn src.api:app --host 0.0.0.0 --port 8000"]
