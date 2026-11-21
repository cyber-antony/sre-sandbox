# Taskmanager mit Docker Compose

Dieses Projekt zeigt eine einfache Anwendung mit Docker Compose.  
Sie besteht aus drei Services:

- `web` – nginx als Webserver
- `taskmanager` – Python-Backend zur Aufgabenverwaltung
- `db` – PostgreSQL-Datenbank

## Voraussetzungen

- Docker
- Docker Compose v2
- Git

## Projekt herunterladen

```bash
cd taskmanager
```

## Anwendung starten

```bash
docker compose up --build
```

Falls der Build-Cache Probleme verursacht:

```bash
docker compose build --no-cache
docker compose up
```

## Anwendung öffnen

Im Browser:

```text
http://localhost:8080
```

## Anwendung stoppen

```bash
docker compose down
```
