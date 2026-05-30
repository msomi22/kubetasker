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
curl http://localhost:8080/readyz
curl http://localhost:8080/startupz
curl http://localhost:8080/version
curl http://localhost:8080/metrics
```

## Build container image

```bash
docker build -t kubetasker-api:local ./api
```

## Run with Docker

```bash
docker run --rm -p 8080:8080 kubetasker-api:local
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
