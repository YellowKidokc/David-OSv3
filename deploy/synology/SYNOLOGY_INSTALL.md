# David-OS Hub — Synology Installation Guide

Two paths to get the Top of Mind API running on your Synology NAS. Pick one.

---

## PATH A: Windows Bundle → Synology (Recommended)

Build the deployment package on Windows, upload to Synology, import as a Container Manager Project.

### Step 1: Build the Bundle on Windows

Open PowerShell in the repo:

```powershell
cd D:\GitHub\David-OS\deploy\synology
.\build_bundle.ps1
```

Output: `dist/top-of-mind-api-synology-bundle.zip`

### Step 2: Upload to Synology

1. Extract `top-of-mind-api-synology-bundle.zip` to a folder on your NAS.
2. Recommended location: `/volume1/docker/david-os/`
3. Create the data directory: `/volume1/docker/david-os/data/`

### Step 3: Set Environment Variables

In Container Manager, when you create the Project, you'll set these in the **Environment Variables** section (or create a `.env` file):

```
FIHUB_API_TOKEN=your-secure-token-here-change-this
FIHUB_PORT=10000
FIHUB_DATA_DIR=/volume1/docker/david-os/data
```

**Important**: The `stack.env` error you hit before happens when Container Manager can't find the env file. To avoid it:
- EITHER: Paste the env vars directly into the Container Manager UI (Project → Environment tab)
- OR: Create a `.env` file in the same folder as `docker-compose.yml` before importing

### Step 4: Deploy as Container Manager Project

1. Open **Container Manager** → **Project** → **Create**
2. Name: `david-os-hub`
3. Path: browse to `/volume1/docker/david-os/` (where you extracted the bundle)
4. Container Manager will auto-detect `docker-compose.yml`
5. Add the environment variables from Step 3
6. **Enable:** "Build the image from Dockerfile" (checked by default)
7. Click **Next** → **Done**

### Step 5: Verify

```powershell
# From PowerShell on Windows (replace with your Synology IP):
$uri = "http://YOUR-SYNOLOGY-IP:10000/openapi.json"
Invoke-RestMethod -Uri $uri -Method GET
```

Or test from the Synology itself:
```bash
ssh admin@YOUR-SYNOLOGY-IP
curl http://localhost:10000/openapi.json
```

---

## PATH B: Direct on Synology (SSH / Git Clone)

If you prefer to keep the full repo on the NAS and update via git pull.

### Step 1: Enable SSH and Git on Synology

```bash
# SSH into your NAS
ssh admin@YOUR-SYNOLOGY-IP

# Install Git (if not already)
sudo synopkg install Git
```

### Step 2: Clone the Repo

```bash
cd /volume1/docker
git clone https://github.com/YellowKidokc/David-OS.git david-os
cd david-os
```

### Step 3: Create the Data Directory

```bash
mkdir -p /volume1/docker/david-os/data
```

### Step 4: Deploy with docker-compose

```bash
cd /volume1/docker/david-os/deploy/synology

# Set your token
export FIHUB_API_TOKEN="your-secure-token-here"

# Build and run
sudo docker compose -f docker-compose.yml up --build -d
```

### Step 5: Verify

```bash
curl http://localhost:10000/openapi.json
curl http://localhost:10000/health
```

---

## PATH C: Container Manager Project with Pre-built Image (Simplest)

Use this if you want zero building on the Synology.

### Step 1: Build the Image on Windows

```powershell
cd D:\GitHub\David-OS\api
docker build -t top-of-mind-api:local .
```

### Step 2: Export and Transfer

```powershell
# Save the image
docker save top-of-mind-api:local | gzip > top-of-mind-api.tar.gz

# Copy to Synology (adjust path as needed)
scp top-of-mind-api.tar.gz admin@YOUR-SYNOLOGY-IP:/volume1/docker/
```

### Step 3: Load on Synology

```bash
ssh admin@YOUR-SYNOLOGY-IP
cd /volume1/docker
gunzip -c top-of-mind-api.tar.gz | sudo docker load
```

### Step 4: Create Project in Container Manager

1. Create a folder: `/volume1/docker/david-os/`
2. Copy `deploy/synology/docker-compose.project.yml` to that folder as `docker-compose.yml`
3. Create `/volume1/docker/david-os/data/`
4. Container Manager → Project → Create
5. Name: `david-os-hub`
6. Path: `/volume1/docker/david-os/`
7. Set `FIHUB_API_TOKEN` in Environment Variables
8. **Uncheck** "Build the image from Dockerfile" (image is already loaded)
9. Deploy

---

## Post-Install: Desk App

The desk app (React frontend) can be run two ways:

### Option 1: Development mode on Windows (points at Synology hub)

```powershell
cd D:\GitHub\David-OS\apps\desk
# Edit .env or set the API URL in the UI
# The desk app defaults to http://127.0.0.1:10000
# Change to your Synology IP in the UI settings panel
npm install
npm run dev
```

### Option 2: Build and serve from Synology (or Cloudflare Pages)

```powershell
cd D:\GitHub\David-OS\apps\desk
npm install
npm run build
# Upload dist/ folder to Synology web station, Cloudflare Pages, or any static host
```

---

## Troubleshooting

### "stack.env: no such file or directory"

This happens when Container Manager can't resolve environment variables. Fixes:
- Make sure `.env` exists in the project folder, OR
- Enter env vars directly in Container Manager's Project → Environment tab, OR
- Use hardcoded values in `docker-compose.yml` instead of `${VAR}` syntax

### "Cannot connect to the Docker daemon"

Make sure Docker/Container Manager is running:
- Synology Package Center → Container Manager → Run

### Port 10000 already in use

Change the port mapping in `docker-compose.yml`:
```yaml
ports:
  - "10001:10000"  # Maps NAS port 10001 to container port 10000
```

### Database permissions

The SQLite file needs write permissions:
```bash
sudo chown -R 1000:1000 /volume1/docker/david-os/data
sudo chmod 755 /volume1/docker/david-os/data
```

---

## API Token Setup

Generate a secure token and set it as `FIHUB_API_TOKEN`:

```powershell
# On Windows — generates a 32-character random token
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
```

Use this token in all API requests via the `Authorization: Bearer <token>` header. The desk app will ask for it on first connect.

---

## What Runs Where

| Component | Runs On | Port | Purpose |
|-----------|---------|------|---------|
| top-of-mind-api (hub) | Synology NAS | 10000 | Core API — conversations, files, memory, agents |
| desk app (React UI) | Windows dev / static host | 5173 (dev) / 80 (prod) | Your daily driver interface |
| AHK bridge | Windows only | — | Clipboard capture, overlays, hotkeys |
| Ollama (optional) | Synology | 11434 | Local LLM inference |

---

## Next Steps After Install

1. **Desk app**: `npm run dev` in `apps/desk/` — set the API URL to your Synology IP:10000
2. **Backup**: Set up a nightly `VACUUM INTO` to `/volume1/backup/david-os/` (see `api/scripts/backup.sh`)
3. **AHK tray agent**: Build the clipboard capture program (60-line AHK script — see `ahk/` folder)
4. **Cloudflare tunnel** (optional): Expose hub securely without opening ports
