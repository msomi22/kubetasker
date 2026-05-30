import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

START_TIME = time.time()
TASKS: List[Dict[str, str]] = []
ALLOWED_STATUSES = {"pending", "in_progress", "completed", "cancelled"}
TRUE_VALUES = {"1", "true", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "no", "n", "off"}
DEFAULT_CONFIG_FILE_PATH = "/etc/kubetasker/app-config.yaml"
DEFAULT_SECRET_FILE_PATH = "/etc/kubetasker/secret/api-token"
METRICS = {
    "tasks_created_total": 0,
    "tasks_updated_total": 0,
    "tasks_deleted_total": 0,
    "readiness_checks_total": 0,
    "readiness_failures_total": 0,
    "liveness_checks_total": 0,
    "liveness_failures_total": 0,
}

logger = logging.getLogger("kubetasker")

app = FastAPI(
    title="KubeTasker API",
    description="Lightweight FastAPI app for CKAD Kubernetes practice.",
    version=os.getenv("APP_VERSION", "0.2.0"),
)


class TaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")


class TaskStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|in_progress|completed|cancelled)$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return default


def configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "info").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    logger.setLevel(level)


def settings() -> Dict[str, str]:
    return {
        "appName": os.getenv("APP_NAME", "KubeTasker"),
        "appMode": os.getenv("APP_MODE", "learning"),
        "appVersion": os.getenv("APP_VERSION", "0.2.0"),
        "taskMode": os.getenv("TASK_MODE", "learning"),
        "logLevel": os.getenv("LOG_LEVEL", "info"),
        "welcomeMessage": os.getenv("WELCOME_MESSAGE", "Welcome to KubeTasker"),
        "enableSampleTasks": str(env_bool("ENABLE_SAMPLE_TASKS", True)).lower(),
        "taskLimit": os.getenv("TASK_LIMIT", "100"),
        "storageMode": os.getenv("STORAGE_MODE", "memory"),
        "startupDelaySeconds": os.getenv("STARTUP_DELAY_SECONDS", "0"),
        "readinessMode": os.getenv("READINESS_MODE", "normal"),
        "livenessMode": os.getenv("LIVENESS_MODE", "normal"),
        "requireSecret": os.getenv("REQUIRE_SECRET", "false"),
        "requireConfigFile": os.getenv("REQUIRE_CONFIG_FILE", "false"),
        "configFilePath": os.getenv("CONFIG_FILE_PATH", DEFAULT_CONFIG_FILE_PATH),
        "secretFilePath": os.getenv("SECRET_FILE_PATH", DEFAULT_SECRET_FILE_PATH),
        "taskStoragePath": os.getenv("TASK_STORAGE_PATH", "/data/tasks.json"),
    }


def task_limit() -> int:
    try:
        return int(os.getenv("TASK_LIMIT", "100"))
    except ValueError:
        return 100


def file_exists(path: str) -> bool:
    return os.path.exists(path) and os.path.isfile(path)


def path_writable(path: str) -> bool:
    directory = path if os.path.isdir(path) else os.path.dirname(path)
    return bool(directory) and os.path.isdir(directory) and os.access(directory, os.W_OK)


def startup_delay_seconds() -> int:
    try:
        return int(os.getenv("STARTUP_DELAY_SECONDS", "0"))
    except ValueError:
        return 0


def startup_complete() -> bool:
    return (time.time() - START_TIME) >= startup_delay_seconds()


def read_secret_token() -> Optional[str]:
    env_token = os.getenv("API_TOKEN")
    if env_token:
        return env_token

    secret_path = settings()["secretFilePath"]
    if file_exists(secret_path):
        try:
            with open(secret_path, "r", encoding="utf-8") as token_file:
                token = token_file.read().strip()
                return token or None
        except OSError:
            return None

    return None


def api_token_configured() -> bool:
    return read_secret_token() is not None


def parse_mounted_config(path: str) -> Dict[str, str]:
    """Parse a tiny CKAD-friendly key/value YAML or properties file.

    This intentionally avoids extra dependencies so learners can mount a simple file such as:

    appMessage: Hello from ConfigMap
    maintenanceMode: false
    """
    if not file_exists(path):
        return {}

    parsed: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as config_file:
        for raw_line in config_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, value = line.split(":", 1)
            elif "=" in line:
                key, value = line.split("=", 1)
            else:
                continue
            parsed[key.strip()] = value.strip().strip('"\'')
    return parsed


def mounted_config() -> Dict[str, object]:
    cfg = settings()
    path = cfg["configFilePath"]
    present = file_exists(path)
    required = cfg["requireConfigFile"].lower() == "true"
    result: Dict[str, object] = {
        "path": path,
        "required": required,
        "present": present,
        "loaded": False,
        "error": None,
        "values": {},
    }

    if not present:
        if required:
            result["error"] = f"required config file is missing at {path}"
        return result

    try:
        result["values"] = parse_mounted_config(path)
        result["loaded"] = True
    except OSError as exc:
        result["error"] = f"mounted config file could not be read: {exc}"

    return result


def public_config_status() -> Dict[str, object]:
    cfg = settings()
    mounted = mounted_config()
    return {
        "appMode": cfg["appMode"],
        "taskMode": cfg["taskMode"],
        "logLevel": cfg["logLevel"],
        "welcomeMessage": cfg["welcomeMessage"],
        "sampleTasksEnabled": env_bool("ENABLE_SAMPLE_TASKS", True),
        "apiTokenConfigured": api_token_configured(),
        "mountedConfigPath": mounted["path"],
        "mountedConfigRequired": mounted["required"],
        "mountedConfigPresent": mounted["present"],
        "mountedConfigLoaded": mounted["loaded"],
        "mountedConfigError": mounted["error"],
    }


def seed_sample_tasks() -> None:
    if not env_bool("ENABLE_SAMPLE_TASKS", True) or TASKS:
        return

    timestamp = now_iso()
    sample_tasks = [
        {
            "id": "sample-read-config",
            "title": "Read runtime config",
            "description": "Use /config/status to inspect non-sensitive runtime configuration.",
            "priority": "normal",
            "status": "pending",
            "createdAt": timestamp,
            "updatedAt": timestamp,
        },
        {
            "id": "sample-check-readiness",
            "title": "Check readiness",
            "description": "Use /ready to verify whether required runtime configuration is valid.",
            "priority": "high",
            "status": "pending",
            "createdAt": timestamp,
            "updatedAt": timestamp,
        },
    ]

    remaining_capacity = max(task_limit() - len(TASKS), 0)
    if remaining_capacity == 0:
        logger.info("Skipping sample task seeding because TASK_LIMIT has no remaining capacity.")
        return

    TASKS.extend(sample_tasks[:remaining_capacity])


def validate_startup_configuration() -> None:
    mounted = mounted_config()
    if mounted["required"] and not mounted["loaded"]:
        raise RuntimeError(mounted["error"] or "required mounted config file is not loaded")


def find_task(task_id: str) -> Dict[str, str]:
    for task in TASKS:
        if task["id"] == task_id:
            return task
    raise HTTPException(status_code=404, detail=f"task {task_id} was not found")


def readiness_state() -> Dict[str, object]:
    cfg = settings()
    mounted = mounted_config()
    checks = {
        "startupComplete": startup_complete(),
        "readinessModeNormal": cfg["readinessMode"].lower() != "fail",
        "requiredConfigFileLoaded": True,
        "requiredSecretPresent": True,
        "storageWritable": True,
    }

    if mounted["required"]:
        checks["requiredConfigFileLoaded"] = bool(mounted["loaded"])

    if cfg["requireSecret"].lower() == "true":
        checks["requiredSecretPresent"] = api_token_configured()

    if cfg["storageMode"].lower() == "file":
        checks["storageWritable"] = path_writable(cfg["taskStoragePath"])

    ready = all(checks.values())
    return {"ready": ready, "checks": checks, "config": public_config_status()}


@app.on_event("startup")
def startup_event():
    configure_logging()
    validate_startup_configuration()
    seed_sample_tasks()
    cfg = public_config_status()
    logger.info(
        "Starting KubeTasker with appMode=%s taskMode=%s logLevel=%s sampleTasksEnabled=%s apiTokenConfigured=%s mountedConfigLoaded=%s",
        cfg["appMode"],
        cfg["taskMode"],
        cfg["logLevel"],
        cfg["sampleTasksEnabled"],
        cfg["apiTokenConfigured"],
        cfg["mountedConfigLoaded"],
    )


@app.get("/")
def root():
    cfg = settings()
    return {
        "app": "KubeTasker",
        "mode": cfg["appMode"],
        "message": cfg["welcomeMessage"],
        "docs": "/docs",
        "health": {
            "basic": "/health",
            "liveness": "/livez",
            "readiness": "/ready",
            "readinessAlias": "/readyz",
            "startup": "/startupz",
        },
        "operations": {
            "version": "/version",
            "config": "/config",
            "configStatus": "/config/status",
            "demoProtected": "/config/demo-protected",
            "secretStatus": "/secret-status",
            "storageStatus": "/storage/status",
            "securityStatus": "/security/status",
            "metrics": "/metrics",
        },
        "tasks": {
            "create": "POST /tasks",
            "list": "GET /tasks",
            "stats": "GET /tasks/stats",
            "getById": "GET /tasks/{task_id}",
            "updateStatus": "PATCH /tasks/{task_id}/status",
            "delete": "DELETE /tasks/{task_id}",
        },
    }


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


def ready_response():
    METRICS["readiness_checks_total"] += 1
    state = readiness_state()
    if not state["ready"]:
        METRICS["readiness_failures_total"] += 1
        raise HTTPException(status_code=503, detail=state)
    return {"status": "ready", "checks": state["checks"]}


@app.get("/ready")
def ready():
    return ready_response()


@app.get("/readyz")
def readyz():
    return ready_response()


@app.get("/startupz")
def startupz():
    if not startup_complete():
        raise HTTPException(status_code=503, detail="startup delay has not completed")
    return {"status": "started"}


@app.get("/version")
def version():
    return {
        "app": "KubeTasker",
        "version": os.getenv("APP_VERSION", "0.2.0"),
        "mode": os.getenv("APP_MODE", "learning"),
    }


@app.get("/config")
def config():
    cfg = settings()
    mounted = mounted_config()
    cfg["configFilePresent"] = mounted["present"]
    cfg["configFileLoaded"] = mounted["loaded"]
    cfg["apiTokenConfigured"] = str(api_token_configured()).lower()
    return cfg


@app.get("/config/status")
def config_status():
    return public_config_status()


@app.get("/config/demo-protected")
def demo_protected(
    request: Request,
    x_api_token: Optional[str] = Header(default=None, alias="X-API-Token"),
):
    expected_token = read_secret_token()
    if not expected_token:
        raise HTTPException(status_code=503, detail="API token is not configured")

    auth_header = request.headers.get("authorization", "")
    bearer_token = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else None
    provided_token = x_api_token or bearer_token

    if provided_token != expected_token:
        raise HTTPException(status_code=401, detail="valid API token is required")

    return {
        "status": "authorized",
        "message": "Secret-backed configuration is working.",
        "secretExposed": False,
    }


@app.get("/secret-status")
def secret_status():
    cfg = settings()
    return {
        "apiTokenEnvPresent": bool(os.getenv("API_TOKEN")),
        "secretFilePresent": file_exists(cfg["secretFilePath"]),
        "apiTokenConfigured": api_token_configured(),
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
    if len(TASKS) >= task_limit():
        raise HTTPException(status_code=409, detail=f"task limit of {task_limit()} has been reached")

    timestamp = now_iso()
    task = {
        "id": str(uuid4()),
        "title": request.title,
        "description": request.description or "",
        "priority": request.priority,
        "status": "pending",
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    TASKS.append(task)
    METRICS["tasks_created_total"] += 1
    return task


@app.get("/tasks")
def list_tasks(status: Optional[str] = None):
    if status and status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"unsupported status: {status}")

    items = [task for task in TASKS if status is None or task["status"] == status]
    return {"items": items, "count": len(items), "total": len(TASKS)}


@app.get("/tasks/stats")
def task_stats():
    by_status = {status: 0 for status in sorted(ALLOWED_STATUSES)}
    by_priority = {"low": 0, "normal": 0, "high": 0, "urgent": 0}

    for task in TASKS:
        by_status[task["status"]] = by_status.get(task["status"], 0) + 1
        by_priority[task["priority"]] = by_priority.get(task["priority"], 0) + 1

    return {
        "total": len(TASKS),
        "limit": task_limit(),
        "remainingCapacity": max(task_limit() - len(TASKS), 0),
        "byStatus": by_status,
        "byPriority": by_priority,
    }


@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    return find_task(task_id)


@app.patch("/tasks/{task_id}/status")
def update_task_status(task_id: str, request: TaskStatusUpdate):
    task = find_task(task_id)
    task["status"] = request.status
    task["updatedAt"] = now_iso()
    METRICS["tasks_updated_total"] += 1
    return task


@app.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    task = find_task(task_id)
    TASKS.remove(task)
    METRICS["tasks_deleted_total"] += 1
    return {"deleted": True, "taskId": task_id}


@app.get("/metrics")
def metrics():
    lines = [f"kubetasker_{name} {value}" for name, value in METRICS.items()]
    lines.append(f"kubetasker_tasks_in_memory {len(TASKS)}")
    lines.append(f"kubetasker_task_limit {task_limit()}")
    return "\n".join(lines) + "\n"
