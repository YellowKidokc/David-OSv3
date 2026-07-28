# Top of Mind PWA

This folder is an exact deployed artifact snapshot pulled from:

`https://top-of-mind.davidokc28.workers.dev`

Captured files:

- `index.html`
- `assets/index-Bldb1RjH.js`
- `assets/index-rk_vmIdF.css`
- `manifest.webmanifest`
- `sw.js`
- `icon-192.png`
- `icon-512.png`

The deployed manifest identifies the app as:

- Name: `Top of Mind`
- Description: `One inbox for every AI.`
- Theme/background: `#0a0a0a`
- Display mode: `standalone`

## Important

This is the real deployed PWA build, not the wrong React `apps/desk` copy and not the older AHK/WebView `ai-hub-v2` stack.

The bundled JavaScript contains source fingerprints such as:

- `src\App.tsx`
- `src\main.tsx`
- `src\components\ui\sonner.tsx`
- Views: `knowledge`, `markdown`, `files`, `operator`, `settings`
- Theme tokens: `tom-bg`, `tom-text`, `tom-border`

The editable source repo was not found yet. Keep this folder as the deployment snapshot until the source project is located.

## Local Use

Open `index.html` directly in a browser, or serve this folder as static files. The app uses relative asset paths and includes a minimal service worker for PWA installability.
