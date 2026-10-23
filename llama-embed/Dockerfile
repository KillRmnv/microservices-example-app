# Local embedding server (llama.cpp, bge-m3). Opt-in via compose profile `llm`:
#   docker compose --profile llm up -d llama-embed
# Needs the model file on the host, e.g. ~/models/bge-m3-q8_0.gguf
# (set LLAMA_MODEL_FILE). Without the profile, point LLAMA_EMBED_URL
# at a host-side `llama server --embedding` instead.
#
# No prebuilt wheel for this image -> compile once (cached layer).
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /wheel
RUN pip wheel --no-cache-dir --wheel-dir=/wheel "llama-cpp-python[server]==0.3.36"

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY --from=builder /wheel /wheel
RUN pip install --no-cache-dir /wheel/llama_cpp_python-*.whl /wheel/*.whl && rm -rf /wheel

ENV LLAMA_MODEL_FILE=/models/bge-m3-q8_0.gguf
ENV LLAMA_EMBED_CTX=512
ENV LLAMA_EMBED_THREADS=6
ENV LLAMA_EMBED_PORT=8088

EXPOSE 8088
USER appuser

ENTRYPOINT ["sh", "-c", "python -m llama_cpp.server --model \"$LLAMA_MODEL_FILE\" --embedding True --n_ctx \"$LLAMA_EMBED_CTX\" --n_threads \"$LLAMA_EMBED_THREADS\" --host 0.0.0.0 --port \"$LLAMA_EMBED_PORT\""]
