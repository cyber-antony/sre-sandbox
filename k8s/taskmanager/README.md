# Taskmanager on k3s

This app is deployed from manifests in this directory.

## Included resources

- `Namespace`
- PostgreSQL `Secret`
- PostgreSQL `PV` + `PVC` backed by NFS on `lab`
- PostgreSQL `Deployment` + `Service`
- backend `Deployment` + `Service`
- frontend `Deployment` + `Service`

## Storage choice

PostgreSQL data is stored on the NFS export from `lab`:

- NFS server: the physical lab host's stable address, taken from `site.lab.address`
- NFS export: `site.postgres.directory` (default `/srv/postgres`)
- app subdirectory inside the export: `taskmanager-postgres`

This keeps DB data away from `mainhost`.

## Apply

```bash
make taskmanager_apply
```

## Delete

```bash
make taskmanager_delete
```

## First access

The frontend is exposed as `NodePort`:

- `http://<control-plane-address>:30080`
- `http://<worker-1-address>:30080`
- `http://<worker-2-address>:30080`

Replace the placeholders with your configured node addresses. The client needs
a route to the internal cluster network through mainhost.

## Important note

The backend is intentionally packaged in a simple lab-friendly way:
- source code comes from a `ConfigMap`
- Python dependencies are installed at container start

This is convenient for learning and first integration.
Later we should replace it with a proper image build and registry flow.
