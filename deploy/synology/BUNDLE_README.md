# Top-of-Mind API Synology Bundle

This folder is the simple Docker install shape for Synology Container Manager.
It is headless: no GUI, no OCR, no AutoHotkey. Those stay on Windows and call
this hub over HTTP.

## Copy To Synology

Copy this whole bundle folder to:

```text
/volume1/docker/top-of-mind-api
```

Expected shape:

```text
/volume1/docker/top-of-mind-api/apps/api
/volume1/docker/top-of-mind-api/docker-compose.yml
/volume1/docker/top-of-mind-api/.env
/volume1/docker/top-of-mind-api/data
```

The bundle builder creates this shape for you from the current David-OS API.

## Start

```sh
cd /volume1/docker/top-of-mind-api
cp .env.example .env
mkdir -p data
```

Edit `.env` and set a real `FIHUB_API_TOKEN`, then:

```sh
docker compose up -d --build
```

## Test From Windows

```powershell
$env:FIHUB_TOKEN = "YOUR_TOKEN"
powershell -ExecutionPolicy Bypass -File .\test_synology_hub.ps1 -BaseUrl http://SYNOLOGY-IP:10000
```

Expected result:

```text
PASS: Synology headless hub is reachable, authenticated, and writing to SQLite-backed routes.
```

## Permission Fix If Container Manager Cannot Write

If the container fails because SQLite or `/data` is not writable, give the
Container Manager/Docker service account read/write permission to:

```text
/volume1/docker/top-of-mind-api
/volume1/docker/top-of-mind-api/data
```

If you are doing it from SSH:

```sh
mkdir -p /volume1/docker/top-of-mind-api/data
chmod 775 /volume1/docker/top-of-mind-api/data
```
