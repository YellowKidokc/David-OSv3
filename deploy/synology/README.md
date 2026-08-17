# Synology Deployment

This folder makes the Top-of-Mind API run as an always-on Synology service.

Preferred first path: use Synology Container Manager with `docker-compose.yml`.

Package Center path: use the SPK skeleton under `spk/` after the container path is proven on your NAS.

## Easiest Path: Build A Bundle On Windows

From Windows, run:

```powershell
powershell -ExecutionPolicy Bypass -File D:\GitHub\David-OS\deploy\synology\build_bundle.ps1
```

That creates:

```text
D:\GitHub\David-OS\deploy\synology\dist\top-of-mind-api
D:\GitHub\David-OS\deploy\synology\dist\top-of-mind-api-synology-bundle.zip
```

Copy the folder or zip contents to:

```text
/volume1/docker/top-of-mind-api
```

Then follow the start steps in the bundle README.

## What Runs On Synology

- Top-of-Mind API on port `10000`
- SQLite hub database on the Synology local volume
- Token-protected LAN API
- Shared message/clipboard/API-call memory for Windows clients

Windows still owns AutoHotkey, OCR, window focus, and typing into local apps.

## Container Manager Install

1. Copy this repo to the Synology, for example:

```text
/volume1/docker/top-of-mind-api/repo
```

2. Create the data folder:

```sh
mkdir -p /volume1/docker/top-of-mind-api/data
```

3. Copy the env file:

```sh
cd /volume1/docker/top-of-mind-api/repo/deploy/synology
cp .env.example .env
```

4. Edit `.env` and set a real `FIHUB_API_TOKEN`.

5. Start:

```sh
docker compose up -d --build
```

If your Synology uses the older compose binary:

```sh
docker-compose up -d --build
```

6. Test from a Windows PC on the LAN:

```powershell
$token = "YOUR_TOKEN"
Invoke-RestMethod http://SYNOLOGY-IP:10000/jobs/stats -Headers @{ "X-API-Token" = $token }
```

Or run the full headless-hub smoke test:

```powershell
$env:FIHUB_TOKEN = "YOUR_TOKEN"
powershell -ExecutionPolicy Bypass -File .\test_synology_hub.ps1 -BaseUrl http://SYNOLOGY-IP:10000
```

That script proves the parts this install is supposed to own:

- token-protected API access,
- SQLite-backed clipboard shelf,
- Top-of-Mind message stream,
- outbound agent routing,
- memory storage.

Open docs:

```text
http://SYNOLOGY-IP:10000/docs
```

## AutoHotkey Client Settings

On each Windows computer:

```text
HubBaseUrl := "http://SYNOLOGY-IP:10000"
```

Keep AutoHotkey, OCR, TypingMind, and window control on Windows. The Synology
container is the always-on headless hub; it does not need a GUI and should not
try to see or type into desktop windows.

Set the token as a Windows environment variable, not in git:

```powershell
[Environment]::SetEnvironmentVariable("FIHUB_TOKEN", "YOUR_TOKEN", "User")
```

Restart AutoHotkey after setting the variable.

## SQLite Rule

Only the API container writes SQLite.

Do not point Windows apps directly at:

```text
/volume1/docker/top-of-mind-api/data/top-of-mind.sqlite3
```

Every client should call the API over HTTP.

## Backups

Back up this folder:

```text
/volume1/docker/top-of-mind-api/data
```

For live SQLite, include:

```text
top-of-mind.sqlite3
top-of-mind.sqlite3-wal
top-of-mind.sqlite3-shm
```

Better later: add a scheduled API-safe backup job that uses SQLite backup tooling.

## Cloudflare Later

After LAN mode is stable, put Cloudflare Tunnel in front of the Synology service.

Do not expose port `10000` directly to the public internet.

## Permission Fix If Container Manager Cannot Write

If the container starts and then fails because SQLite or `/data` is not writable,
fix permissions on the Synology folder:

```sh
mkdir -p /volume1/docker/top-of-mind-api/data
chmod 775 /volume1/docker/top-of-mind-api/data
```

If you are using Simple Permission Manager, grant the Container Manager/Docker
service account read/write access to:

```text
/volume1/docker/top-of-mind-api
/volume1/docker/top-of-mind-api/data
```

The data folder is the only place this container should need to write.
