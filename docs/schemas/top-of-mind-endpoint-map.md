# Top-of-Mind Endpoint Map

This file captures the endpoints already expected by the imported React cockpit.

Source:

`integrations/top-of-mind-source/apps/desk/src/lib/api/topOfMindApi.js`

## Current React Expectations

| Method | Route | TOP AI FIS Area |
| --- | --- | --- |
| `GET` | `/jobs/stats` | hub health / jobs |
| `GET` | `/capabilities` | hub capabilities |
| `GET` | `/top-of-mind/sources` | agent/source registry |
| `POST` | `/top-of-mind/sources` | agent/source registry |
| `GET` | `/top-of-mind/messages` | message stream |
| `POST` | `/top-of-mind/messages` | message stream |
| `PATCH` | `/top-of-mind/messages/{id}` | message stream |
| `POST` | `/top-of-mind/combine` | message/wall combine |
| `POST` | `/top-of-mind/controls/end-all` | stop all agents/jobs |
| `POST` | `/clipboard/save` | clipboard |
| `POST` | `/agents/send` | dispatch |
| `POST` | `/bridge/jobs` | AHK bridge |
| `GET` | `/bridge/jobs` | AHK bridge |
| `POST` | `/bridge/heartbeat` | AHK bridge |
| `POST` | `/bridge/events` | AHK bridge |
| `GET` | `/folders` | folders |
| `POST` | `/folders` | folders |
| `POST` | `/memory/items` | memory |
| `GET` | `/memory/items` | memory |
| `GET` | `/memory/search` | memory search |
| `POST` | `/memory/embed-pending` | vectorization |
| `POST` | `/files/cache` | file cache |
| `GET` | `/files/cache` | file cache |
| `GET` | `/files/cache/search` | file search |
| `GET` | `/files/cache/by-path` | file cache |
| `POST` | `/semantic/score` | semantic addressing |
| `POST` | `/operator/file-actions` | file action proposals |
| `POST` | `/operator/commands` | command jobs |

## Deployment Shape

For public/NAS deployment:

```text
https://memory.dlowehomelab.com/      -> React cockpit
https://memory.dlowehomelab.com/api   -> Hub API
```

The React app can use:

```text
VITE_TOP_OF_MIND_API=https://memory.dlowehomelab.com/api
```

or a saved local override while testing.
