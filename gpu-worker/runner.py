import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

from google.cloud import firestore, storage

COMFY_URL = "http://127.0.0.1:8188"
WORK_DIR = Path("/tmp/job_work")
COMFY_INPUT_DIR = Path("/opt/ComfyUI/input")
COMFY_OUTPUT_DIR = Path("/opt/ComfyUI/output")
COMFY_MODELS_DIR = Path("/opt/ComfyUI/models")


def update_firestore_job(job_id: str, fields: dict[str, Any]) -> None:
    project_id = os.environ.get("GCP_PROJECT_ID")
    if not project_id:
        return
    try:
        db = firestore.Client(project=project_id)
        db.collection("jobs").document(job_id).set(fields, merge=True)
    except Exception as exc:
        print(f"[runner] Warning: Firestore update failed: {exc}", file=sys.stderr)


def sync_models_from_gcs(bucket_name: str, workflow: dict[str, Any]) -> None:
    """Download referenced model checkpoints from gs://<bucket>/models/ into ComfyUI models dir."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # Sync any checkpoint named in CheckpointLoaderSimple nodes
    for node in workflow.values():
        if isinstance(node, dict) and node.get("class_type") == "CheckpointLoaderSimple":
            ckpt_name = node.get("inputs", {}).get("ckpt_name")
            if not ckpt_name:
                continue
            dest = COMFY_MODELS_DIR / "checkpoints" / ckpt_name
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            for prefix in (f"models/checkpoints/{ckpt_name}", f"checkpoints/{ckpt_name}"):
                blob = bucket.blob(prefix)
                if blob.exists():
                    print(f"[runner] Downloading gs://{bucket_name}/{prefix} -> {dest}")
                    blob.download_to_filename(str(dest))
                    break


def download_gcs_inputs(bucket_name: str, input_uris: list[str]) -> dict[str, Path]:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    downloaded: dict[str, Path] = {}
    COMFY_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    for uri in input_uris:
        clean = uri.replace(f"gs://{bucket_name}/", "").lstrip("/")
        local_name = Path(clean).name
        dest = COMFY_INPUT_DIR / local_name
        bucket.blob(clean).download_to_filename(str(dest))
        downloaded[clean] = dest
    return downloaded


def submit_comfy_workflow(workflow: dict[str, Any]) -> str:
    payload = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFY_URL}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["prompt_id"]


def poll_comfy_history(prompt_id: str, timeout_sec: int = 3000) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}", timeout=15) as resp:
            history = json.loads(resp.read().decode("utf-8"))
            if prompt_id in history:
                return history[prompt_id]
        time.sleep(2)
    raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out")


def encode_1080p_mp4(input_video: Path, output_video: Path, vertical: bool) -> Path:
    scale = "1080:1920" if vertical else "1920:1080"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_video),
        "-vf",
        f"scale={scale}:force_original_aspect_ratio=decrease,pad={scale}:(ow-iw)/2:(oh-ih)/2",
        "-r",
        "25",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(output_video),
    ]
    subprocess.run(cmd, check=True)
    return output_video


def main() -> int:
    job_id = os.environ["JOB_ID"]
    bucket_name = os.environ["GCS_BUCKET"]
    workflow_name = os.environ["WORKFLOW_TYPE"]
    output_prefix = os.environ["OUTPUT_PREFIX"].rstrip("/")
    model_config = json.loads(os.environ.get("MODEL_CONFIG_JSON", "{}"))

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    workflow_path = Path("/worker/workflows") / workflow_name
    if not workflow_path.exists():
        raise FileNotFoundError(f"Unknown workflow: {workflow_name}")

    update_firestore_job(job_id, {"state": "running", "progress": 30, "status_message": "Loading ComfyUI workflow"})

    input_paths = [
        p
        for p in (
            model_config.get("portrait_path"),
            model_config.get("reference_image_path"),
            model_config.get("audio_path"),
        )
        if p
    ]
    downloaded = download_gcs_inputs(bucket_name, input_paths)

    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    sync_models_from_gcs(bucket_name, workflow)
    # Inject only validated fields
    if "prompt_node" in workflow and "prompt" in model_config:
        workflow["prompt_node"]["inputs"]["text"] = str(model_config["prompt"])
    if "negative_node" in workflow and "negative_prompt" in model_config:
        workflow["negative_node"]["inputs"]["text"] = str(model_config["negative_prompt"])
    if "sampler_node" in workflow and model_config.get("seed") is not None:
        workflow["sampler_node"]["inputs"]["seed"] = int(model_config["seed"])
    if "image_loader" in workflow and model_config.get("reference_image_path"):
        workflow["image_loader"]["inputs"]["image"] = downloaded[model_config["reference_image_path"]].name

    prompt_id = submit_comfy_workflow(workflow)
    history = poll_comfy_history(prompt_id)

    update_firestore_job(job_id, {"state": "uploading", "progress": 90, "status_message": "Uploading outputs"})

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    uploaded_assets = []
    outputs = history.get("outputs", {})
    for _node_id, node_out in outputs.items():
        for key in ("images", "gifs", "videos"):
            for item in node_out.get(key, []):
                local_file = COMFY_OUTPUT_DIR / item.get("subfolder", "") / item["filename"]
                if not local_file.exists():
                    continue
                if local_file.suffix.lower() in (".mp4", ".mov", ".webm") and workflow_name in (
                    "talking_portrait.json",
                    "wan_video.json",
                ):
                    is_vert = model_config.get("orientation") == "vertical" or model_config.get("aspect_ratio") == "9:16"
                    finished = WORK_DIR / f"final_{local_file.stem}.mp4"
                    local_file = encode_1080p_mp4(local_file, finished, is_vert)

                obj_path = f"{output_prefix}/{local_file.name}"
                bucket.blob(obj_path).upload_from_filename(str(local_file))
                uploaded_assets.append({"filename": local_file.name, "object_path": obj_path})

    manifest = {"job_id": job_id, "workflow": workflow_name, "assets": uploaded_assets}
    bucket.blob(f"{output_prefix}/result.json").upload_from_string(
        json.dumps(manifest, indent=2), content_type="application/json"
    )
    update_firestore_job(job_id, {"state": "completed", "progress": 100, "status_message": "Completed"})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        job_id = os.environ.get("JOB_ID")
        if job_id:
            update_firestore_job(
                job_id,
                {"state": "failed", "status_message": "GPU worker failed", "error_message": str(exc)},
            )
        print(f"[runner] Fatal error: {exc}", file=sys.stderr)
        sys.exit(1)
