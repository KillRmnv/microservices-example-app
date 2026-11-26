# Local llama.cpp servers (bge-m3 embeddings + chat models) via the `llm`
# compose profile. Models are mounted read-only from the host:
#   docker compose --profile llm up -d llama-embed
#
# Built from llama.cpp master: PyPI llama-cpp-python still bundles an older
# runtime without `lfm3` support, and we need it for LFM3-1.7B.
FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        git cmake build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone --depth 1 https://github.com/ggml-org/llama.cpp.git
RUN cmake -S llama.cpp -B llama.cpp/build \
        -DCMAKE_BUILD_TYPE=Release \
        -DGGML_NATIVE=OFF \
        -DLLAMA_CURL=OFF \
        -DLLAMA_BUILD_TESTS=OFF \
        -DLLAMA_BUILD_EXAMPLES=OFF \
    && cmake --build llama.cpp/build --target llama-server -j"$(nproc)"

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 ca-certificates libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY --from=builder /src/llama.cpp/build/bin/ /opt/llama/
ENV LD_LIBRARY_PATH=/opt/llama
ENV PATH=/opt/llama:$PATH

ENV LLAMA_MODEL_FILE=/models/bge-m3-q8_0.gguf
ENV LLAMA_CTX=512
ENV LLAMA_THREADS=6
ENV LLAMA_PORT=8088
ENV LLAMA_EXTRA_ARGS="--embedding"

EXPOSE 8088 8089
USER appuser

ENTRYPOINT ["sh", "-c", "llama-server --model \"$LLAMA_MODEL_FILE\" --ctx-size \"$LLAMA_CTX\" --threads \"$LLAMA_THREADS\" --host 0.0.0.0 --port \"$LLAMA_PORT\" $LLAMA_EXTRA_ARGS"]
