# Kubernetes Manifests

This directory stores Kubernetes manifests that are treated as source of truth
for workloads deployed from `mainhost`.

## Workflow

Sync one app directory to `mainhost`:

```bash
make k8s_sync K8S_APP=taskmanager
```

Apply one app directory on the cluster:

```bash
make k8s_apply K8S_APP=taskmanager
```

Delete one app directory from the cluster:

```bash
make k8s_delete K8S_APP=taskmanager
```

Shortcut targets for the first lab app:

```bash
make taskmanager_apply
make taskmanager_delete
```

## Notes

- manifests are rendered on `mainhost` by `70-k3s-app.yml` using `ansible/environment.yml`
- `kubectl` is executed on `mainhost`
- PostgreSQL data for `taskmanager` is stored on the NFS export from `lab`
- the current first access path for the web UI is a `NodePort` service

The source YAML includes environment templates. Use the Make targets to render
them before applying; do not apply the unrendered source directory directly.
