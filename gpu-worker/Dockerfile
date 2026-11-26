FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    COMFY_DIR=/opt/ComfyUI \
    COMFY_COMMIT=v0.3.10

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv git ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch ${COMFY_COMMIT} https://github.com/Comfy-Org/ComfyUI.git ${COMFY_DIR} \
    && pip3 install --no-cache-dir -r ${COMFY_DIR}/requirements.txt \
    && pip3 install --no-cache-dir \
        google-cloud-storage==2.19.0 \
        google-cloud-firestore==2.19.0 \
        httpx==0.28.1

WORKDIR /worker
COPY entrypoint.sh runner.py ./
COPY workflows/ ./workflows/
RUN chmod +x /worker/entrypoint.sh

# Never expose port 8188 publicly; ComfyUI is bound strictly to 127.0.0.1 inside the batch job.
ENTRYPOINT ["/worker/entrypoint.sh"]
