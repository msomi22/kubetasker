# KubeTasker

KubeTasker is a lightweight FastAPI training app for hands-on CKAD practice through one incremental Kubernetes project.

The project is intentionally designed to help learners practice Kubernetes application developer skills by deploying, configuring, exposing, debugging, securing, and operating one realistic application over multiple stages.

## Why KubeTasker exists

CKAD preparation should not only be theory or disconnected YAML snippets. KubeTasker gives learners one evolving application that can be used to practice:

- Pods and Deployments
- Services and Kubernetes DNS
- ConfigMaps and Secrets
- Environment variables and mounted files
- Readiness, liveness, and startup probes
- Logs, events, exec, and troubleshooting
- Jobs and CronJobs
- Volumes, emptyDir, and PVC-backed storage
- SecurityContext and non-root execution
- Resource requests and limits
- Timed CKAD-style verification habits

## Current status

This repository starts with the foundation API and base Kubernetes manifests.

The first implementation uses **Python FastAPI** because it is lightweight, starts quickly, and is easy to use for CKAD probe, config, storage, security, and debugging scenarios.

## Local API development

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Verify:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/livez
curl http://localhost:8080/ready
curl http://localhost:8080/readyz
curl http://localhost:8080/startupz
curl http://localhost:8080/version
curl http://localhost:8080/config/status
curl http://localhost:8080/metrics
```

## Runtime configuration

KubeTasker supports safe runtime configuration for CKAD ConfigMap, Secret, env var, mounted file, command/args, and probe lessons.

### Environment variables

| Variable | Default | Sensitive | Purpose |
| --- | --- | --- | --- |
| `LOG_LEVEL` | `info` | No | Controls application logging level. |
| `APP_MODE` | `learning` | No | Shows which app mode is active. |
| `TASK_MODE` | `learning` | No | Shows which task behavior mode is active. |
| `ENABLE_SAMPLE_TASKS` | `true` | No | Seeds demo tasks when enabled. |
| `WELCOME_MESSAGE` | `Welcome to KubeTasker` | No | Changes the root endpoint welcome message. |
| `APP_NAME` | `KubeTasker` | No | Application display name. |
| `APP_VERSION` | `0.2.0` | No | Application version shown by `/version`. |
| `TASK_LIMIT` | `100` | No | Maximum number of in-memory tasks. |
| `READINESS_MODE` | `normal` | No | Set to `fail` to simulate readiness failure. |
| `LIVENESS_MODE` | `normal` | No | Set to `fail` to simulate liveness failure. |
| `STARTUP_DELAY_SECONDS` | `0` | No | Simulates delayed startup. |
| `REQUIRE_CONFIG_FILE` | `false` | No | When `true`, startup and readiness require the mounted config file. |
| `CONFIG_FILE_PATH` | `/etc/kubetasker/app-config.yaml` | No | Path to an optional mounted config file. |
| `REQUIRE_SECRET` | `false` | No | When `true`, readiness requires `API_TOKEN` or a secret file. |
| `API_TOKEN` | unset | Yes | Secret token for `/config/demo-protected`. Never logged or returned. |
| `SECRET_FILE_PATH` | `/etc/kubetasker/secret/api-token` | Yes | Optional file-based token location. |
| `STORAGE_MODE` | `memory` | No | Set to `file` to require writable task storage path. |
| `TASK_STORAGE_PATH` | `/data/tasks.json` | No | File storage path checked when `STORAGE_MODE=file`. |

Startup logs include only non-sensitive values and secret presence. Secret values are never printed in logs or API responses.

### Mounted config file

By default, KubeTasker looks for an optional mounted config file at:

```text
/etc/kubetasker/app-config.yaml
```

The file may use simple YAML-style or properties-style key/value lines:

```yaml
appMessage: Hello from a mounted ConfigMap
maintenanceMode: false
```

If `REQUIRE_CONFIG_FILE=false`, the app starts even when the file is absent.

If `REQUIRE_CONFIG_FILE=true`, the app fails clearly during startup when the file is missing or unreadable, and readiness also reports the failed config state.

### Safe config status

Use this endpoint to verify runtime configuration without leaking secrets:

```bash
curl http://localhost:8080/config/status
```

Example response:

```json
{
  "appMode": "learning",
  "taskMode": "learning",
  "logLevel": "info",
  "welcomeMessage": "Welcome to KubeTasker",
  "sampleTasksEnabled": true,
  "apiTokenConfigured": true,
  "mountedConfigPath": "/etc/kubetasker/app-config.yaml",
  "mountedConfigRequired": false,
  "mountedConfigPresent": true,
  "mountedConfigLoaded": true,
  "mountedConfigError": null
}
```

### Secret-backed protected demo endpoint

Set a token with an environment variable or mounted Secret file:

```bash
API_TOKEN=change-me
```

Then call:

```bash
curl -H 'X-API-Token: change-me' http://localhost:8080/config/demo-protected
```

Bearer tokens are also supported:

```bash
curl -H 'Authorization: Bearer change-me' http://localhost:8080/config/demo-protected
```

The endpoint only reports whether authorization succeeded. It never returns the configured token.

### Readiness and liveness

`/health` is a simple liveness-style endpoint.

`/ready` and `/readyz` return healthy only when required runtime configuration is valid. Readiness checks include startup delay, readiness simulation mode, required config file, required secret, and writable storage when file storage mode is enabled.

### Startup command and args

The default container command is:

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

For CKAD lessons, learners can override container `args` safely when the command remains `uvicorn` and the app import target remains `app.main:app`.

Example Kubernetes args override:

```yaml
args:
  - app.main:app
  - --host
  - 0.0.0.0
  - --port
  - "8080"
```

Bad command or args values should fail clearly in pod logs, which is useful for debugging practice.

## Build container image

```bash
docker build -t kubetasker-api:local ./api
```

Versioned image for the runtime configuration labs:

```bash
docker build -t msomi22/kubetasker-api:0.2.0 ./api
docker push msomi22/kubetasker-api:0.2.0
```

## Run with Docker

```bash
docker run --rm -p 8080:8080 kubetasker-api:local
```

Runtime configuration example:

```bash
docker run --rm -p 8080:8080 \
  -e APP_MODE=learning \
  -e TASK_MODE=learning \
  -e ENABLE_SAMPLE_TASKS=true \
  -e WELCOME_MESSAGE='Welcome from Docker runtime config' \
  -e API_TOKEN=change-me \
  kubetasker-api:local
```

## Deploy to Kubernetes

For a local cluster such as kind or minikube:

```bash
kubectl apply -f manifests/base/namespace.yaml
kubectl apply -f manifests/base/api-deployment.yaml
kubectl apply -f manifests/base/api-service.yaml
kubectl apply -f manifests/base/client-pod.yaml
```

Verify:

```bash
kubectl -n kubetasker get pods
kubectl -n kubetasker get svc
kubectl -n kubetasker exec kube-tasker-client -- wget -qO- http://kube-tasker-api:8080/health
kubectl -n kubetasker exec kube-tasker-client -- wget -qO- http://kube-tasker-api:8080/config/status
```

## Incremental CKAD stages

The intended learning path is:

1. Project foundation: deploy the base API and Service
2. Runtime configuration: add ConfigMaps, Secrets, env vars, and mounted files
3. Health and rollout: add startup, readiness, and liveness probes
4. Networking: connect client, API, and worker through Services
5. Batch workloads: add Job and CronJob reporting
6. Storage: add emptyDir and PVC-backed file storage
7. Security: harden the app with securityContext
8. Observability and debugging: diagnose broken integrated manifests
9. Reliability: add resources, replicas, and scheduling constraints
10. Capstone: rebuild and fix the full system under timed CKAD-style conditions

## License

MIT, unless changed later.
