# ICare API + inference engine (CPU). Build from the repository root:
#   docker build -f deployment/Dockerfile -t icare-api .
# See deployment/README.md. The frontend is packaged separately once it exists.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # rtmlib caches YOLOX/RTMPose weights under $TORCH_HOME/hub/checkpoints.
    TORCH_HOME=/opt/icare/model-cache \
    ICARE_API_DATA_DIR=/data \
    ICARE_POSEC3D_MODEL=/app/models/posec3d_fall.onnx \
    ICARE_EXAMPLES_MANIFEST=/app/examples/catalog.json

WORKDIR /app

COPY deployment/requirements-runtime.txt deployment/rtmlib.txt /tmp/deps/
RUN pip install -r /tmp/deps/requirements-runtime.txt \
 && pip install --no-deps -r /tmp/deps/rtmlib.txt \
 && rm -rf /tmp/deps

COPY icare_app/ icare_app/
COPY api/ api/
COPY models/ models/
COPY examples/ examples/

# 1 (default): download the pose weights now and load the full engine once, so
# the image starts ready without network access and a broken model fails the
# build instead of the first visitor. 0: skip; /ready then needs the host to
# reach the model URLs in icare_app/pose.py at startup.
ARG PRELOAD_MODELS=1
RUN mkdir -p "$TORCH_HOME" \
 && if [ "$PRELOAD_MODELS" = "1" ]; then \
      python -c "from icare_app.engine import load_engine; load_engine({'model_path': '$ICARE_POSEC3D_MODEL', 'device': 'cpu'}).close()"; \
    fi

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin icare \
 && mkdir -p /data && chown icare /data
USER icare
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"

# One worker process: the API runs one bounded inference job at a time.
CMD ["uvicorn", "api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
