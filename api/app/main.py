import os
import time
from typing import Dict, List
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

START_TIME = time.time()
TASKS: List[Dict[str, str]] = []
METRICS = {
    "tasks_created_total": 0,
    "readiness_checks_total": 0,
    "readiness_failures_total": 0,
    "liveness_checks_total": 0,
    "liveness_failures_total": 0,
}

app = FastAPI(
    title="KubeTasker API",
    description="Lightweight FastAPI app for CKAD Kubernetes practice.",
    version=os.getenv("APP_VERSION", "0.1.0"),
)


class TaskRequest(BaseModel):
    title: str
    priority: str = "normal"


def settings() -> Dict[str, str]:
    return {
        "appName": os.getenv("APP_NAME", "KubeTasker"),
        "appMode": os.getenv("APP_MODE", "training"),
        "appVersion": os.getenv("APP_VERSION", "0.1.0"),
        "storageMode": os.getenv("STORAGE_MODE", "memory"),
        "startupDelaySeconds": os.getenv("STARTUP_DELAY_SECONDS", "0"),
        "readinessMode": os.getenv("READINESS_MODE", "normal"),
        "livenessMode": os.getenv("LIVENESS_MODE", "normal"),
        "requireSecret": os.getenv("REQUIRE_SECRET", "false"),
        "requireConfigFile": os.getenv("REQUIRE_CONFIG_FILE", "false"),
        "configFilePath": os.getenv("CONFIG_FILE_PATH", "/etc/kubetasker/config/app.properties"),
        "secretFilePath": os.getenv("SECRET_FILE_PATH", "/etc/kubetasker/secret/api-token"),
        "taskStoragePath": os.getenv("TASK_STORAGE_PATH", "/data/tasks.json"),
    }


def file_exists(path: str) -> bool:
    return os.path.exists(path) and os.path.isfile(path)


def path_writable(path: str) -> bool:
    directory = path if os.path.isdir(path) else os.path.dirname(path)
    return bool(directory) and os.path.isdir(directory) and os.access(directory, os.W_OK)


def startup_complete() -> bool:
    delay = int(os.getenv("STARTUP_DELAY_SECONDS", "0"))
    return (time.time() - START_TIME) >= delay


def readiness_state() -> Dict[str, object]:
    cfg = settings()
    checks = {
        "startupComplete": startup_complete(),
        "readinessModeNormal": cfg["readinessMode"].lower() != "fail",
        "requiredConfigFilePresent": True,
        "requiredSecretPresent": True,
        "storageWritable": True,
    }

    if cfg["requireConfigFile"].lower() == "true":
        checks["requiredConfigFilePresent"] = file_exists(cfg["configFilePath"])

    if cfg["requireSecret"].lower() == "true":
        checks["requiredSecretPresent"] = bool(os.getenv("API_TOKEN")) or file_exists(cfg["secretFilePath"])

    if cfg["storageMode"].lower() == "file":
        checks["storageWritable"] = path_writable(cfg["taskStoragePath"])

    ready = all(checks.values())
    return {"ready": ready, "checks": checks}


@app.get("/health")
def health():
    return {"status": "ok", "app": "KubeTasker"}


@app.get("/livez")
def livez():
    METRICS["liveness_checks_total"] += 1
    if os.getenv("LIVENESS_MODE", "normal").lower() == "fail":
        METRICS["liveness_failures_total"] += 1
        raise HTTPException(status_code=500, detail="liveness simulation is failing")
    return {"status": "alive"}


@app.get("/readyz")
def readyz():
    METRICS["readiness_checks_total"] += 1
    state = readiness_state()
    if not state["ready"]:
        METRICS["readiness_failures_total"] += 1
        raise HTTPException(status_code=503, detail=state)
    return {"status": "ready", "checks": state["checks"]}


@app.get("/startupz")
def startupz():
    if not startup_complete():
        raise HTTPException(status_code=503, detail="startup delay has not completed")
    return {"status": "started"}


@app.get("/version")
def version():
    return {
        "app": "KubeTasker",
        "version": os.getenv("APP_VERSION", "0.1.0"),
        "mode": os.getenv("APP_MODE", "training"),
    }


@app.get("/config")
def config():
    cfg = settings()
    cfg["configFilePresent"] = file_exists(cfg["configFilePath"])
    return cfg


@app.get("/secret-status")
def secret_status():
    cfg = settings()
    return {
        "apiTokenEnvPresent": bool(os.getenv("API_TOKEN")),
        "secretFilePresent": file_exists(cfg["secretFilePath"]),
        "rawSecretExposed": False,
    }


@app.get("/storage/status")
def storage_status():
    cfg = settings()
    return {
        "storageMode": cfg["storageMode"],
        "taskStoragePath": cfg["taskStoragePath"],
        "storageWritable": path_writable(cfg["taskStoragePath"]),
        "taskCount": len(TASKS),
    }


@app.get("/security/status")
def security_status():
    cfg = settings()
    return {
        "uid": os.getuid(),
        "gid": os.getgid(),
        "canWriteTmp": path_writable("/tmp/kubetasker.tmp"),
        "canWriteData": path_writable(cfg["taskStoragePath"]),
        "storagePathWritable": path_writable(cfg["taskStoragePath"]),
    }


@app.post("/tasks", status_code=201)
def create_task(request: TaskRequest):
    task = {
        "id": str(uuid4()),
        "title": request.title,
        "priority": request.priority,
        "status": "pending",
    }
    TASKS.append(task)
    METRICS["tasks_created_total"] += 1
    return task


@app.get("/tasks")
def list_tasks():
    return {"items": TASKS, "count": len(TASKS)}


@app.get("/metrics")
def metrics():
    lines = [f"kubetasker_{name} {value}" for name, value in METRICS.items()]
    lines.append(f"kubetasker_tasks_in_memory {len(TASKS)}")
    return "\n".join(lines) + "\n"
