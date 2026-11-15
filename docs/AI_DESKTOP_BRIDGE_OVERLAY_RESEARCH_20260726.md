# AI Desktop Bridge Overlay Research - 2026-07-26

Status: research captured, ready for implementation planning.

Update 2026-07-26:

- `D:\GitHub\David-OS\ahk\overlay\bound_bridge_api_ready.ahk` was hardened into the first runnable tonight build.
- Added persistent mappings through `settings.json`.
- Added overlay logging to `D:\GitHub\David-OS\ahk\overlay\logs\bound_bridge.log`.
- Added fallback input click when UI Automation cannot focus the composer.
- Added send-mode cycling: `enter`, `click`, `ctrl-enter`.
- Added launcher/test/troubleshooting scripts:
  - `START_AI_DESKTOP_BRIDGE.bat`
  - `SEND_TEST_TO_BRIDGE.bat`
  - `TROUBLESHOOT_AI_DESKTOP_BRIDGE.bat`
  - `README_AI_DESKTOP_BRIDGE_TONIGHT.md`
- Verified AutoHotkey validation passes.
- Verified `http://localhost:8765/health` returns OK.
- Verified a test `POST /send` queues and the AHK overlay reads the inbox message.

## Goal

Build one local hub that can route David's messages into multiple desktop AI apps without paying API costs for every conversation. The hub should talk to desktop Claude, ChatGPT, Kimi, Codex, and similar apps by targeting their existing chat input boxes and send buttons.

The desired user experience is:

- David opens or focuses a desktop AI app.
- A small AutoHotkey overlay attaches to that app's chat area.
- The overlay can be click-through for normal typing and mouse use.
- David can type in one hub and route a message to one or more AI apps.
- Each app receives the text through its real desktop UI.
- Replies can later be captured back into the hub by region capture, UI Automation, OCR, or both.

## Existing Local Code

The best local starting point is already in `D:\GitHub\David-OS\ahk\overlay`.

Important files:

- `D:\GitHub\David-OS\ahk\CODEX_BUILD_PROMPT.md`
  - Strongest current spec for Overlay v2.
  - Calls for `ShinsOverlayClass`, per-AI profiles, a local HTTP bridge, an inbox handoff, mapping mode, and reliable message delivery.
- `D:\GitHub\David-OS\ahk\overlay\bound_bridge_api_ready.ahk`
  - Closest current implementation.
  - Already knows targets for Claude, Codex, GPT, and Kimi.
  - Has lock/aim behavior, UIA delivery first, coordinate fallback, and `_inbox` polling.
- `D:\GitHub\David-OS\ahk\overlay\bridge_api.py`
  - FastAPI bridge.
  - Supports `GET /health` and `POST /send`.
  - Writes JSON inbox files into `D:\GitHub\David-OS\ahk\overlay\_inbox`.
- `D:\GitHub\David-OS\bridges\ahk\ai_chat_controller.ahk`
  - Older floating controller.
  - Useful reference for profiles, paste/send behavior, and command UI.
- `D:\GitHub\David-OS\ahk\overlay\lib\UIA.ahk`
  - UI Automation wrapper already present locally.

## Research Findings

Electron desktop AI apps are plausible automation targets, but they will not all expose controls consistently. Claude, ChatGPT, Kimi, Codex, and related apps may be Electron or Chromium-backed, but each app can differ in accessible names, button labels, focus behavior, and update cadence.

The reliable design should therefore not depend on only one detection method.

Recommended fallback chain:

1. Window profile:
   - Track target by exe, title, class, and HWND.
   - Store app profiles for Claude, ChatGPT, Kimi, Codex, and future desktop apps.
2. UI Automation first:
   - Try to find the document/edit/input control.
   - Try to find the Send button by role/name.
   - This is the cleanest path when Electron exposes Chromium accessibility correctly.
3. OCR second:
   - Use OCR over the lower composer region to detect words/icons such as Send, Ask, message box, microphone, or attached controls.
   - This helps when UIA does not expose reliable names.
4. Saved relative coordinates third:
   - Mapping mode lets David drag/select the real text box and send button once.
   - Save coordinates relative to the target window client area, not absolute screen coordinates.
   - This survives normal window moves and monitor changes better than raw screen positions.
5. Clipboard paste delivery:
   - For sending text, focus the mapped/input control, paste through clipboard, verify length when possible, then press Enter or click Send depending on profile.
6. Capture later:
   - Capture replies by UIA text extraction when available.
   - Fall back to OCR on a mapped reply region.
   - Do not block the first working send bridge on perfect capture.

## Overlay Requirements

The overlay should be click-through during normal use. That means the overlay can show controls or outlines but should let mouse and keyboard input pass to the AI app underneath unless David explicitly enters mapping/edit mode.

Use a hotkey or visible toggle for modes:

- Normal mode: overlay stays on top, click-through, non-activating.
- Mapping mode: overlay becomes interactive so David can drag/select target regions.
- Send mode: overlay accepts typed text or receives inbox API text and dispatches it to the selected app.

## Recommended Build Plan

1. Back up `D:\GitHub\David-OS\ahk\overlay`.
2. Start from `bound_bridge_api_ready.ahk`, not from scratch.
3. Keep `bridge_api.py` as the local API boundary:
   - `POST /send` with `{ "target": "claude", "text": "..." }`.
   - Later add multi-target routing with `{ "targets": ["claude", "gpt"], "text": "..." }`.
4. Add a `settings.json` profile store:
   - exe name
   - window title match
   - UIA selectors
   - mapped input rectangle
   - mapped send point
   - send method: click, enter, ctrl-enter
5. Add mapping mode:
   - Attach overlay to active target window.
   - Let David mark input area and send button.
   - Save client-relative coordinates.
6. Add delivery hardening:
   - Focus target app.
   - Click/focus input point.
   - Paste text.
   - Verify pasted text length where possible.
   - Retry once.
   - Send.
7. Add logging:
   - successful target lock
   - UIA match/miss
   - OCR match/miss
   - fallback used
   - delivery result
8. Add launcher scripts:
   - start bridge API
   - start overlay
   - health check
   - open logs

## Risks

- Electron accessibility can change after desktop app updates.
- Some apps expose controls through Chromium accessibility only when accessibility is enabled.
- Button labels can change or be icon-only, which makes OCR and UIA naming less reliable.
- Send behavior differs by app: Enter, Ctrl+Enter, button click, or custom shortcut.
- Screen scaling and multi-monitor movement can break absolute coordinates, so store all manual mappings relative to the client window.

## Implementation Decision

Use a layered system:

- UIA for clean automation.
- OCR for recognition when UIA is blind.
- Saved coordinates as the durable fallback.
- Click-through overlay for normal use.
- Interactive overlay only while mapping or editing.

This matches David's requirement: the overlay can sit on top of the AI app without blocking mouse or keyboard use, but can still become interactive long enough to teach the system where the input and send controls are.

## Sources

- Microsoft Window Features: https://learn.microsoft.com/en-us/windows/win32/winmsg/window-features
- Microsoft Extended Window Styles: https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles
- Electron Accessibility: https://www.electronjs.org/docs/latest/tutorial/accessibility
- Microsoft UI Automation overview: https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-msaa
- Descolada UIA-v2: https://github.com/Descolada/UIA-v2
- Descolada OCR for AutoHotkey v2: https://github.com/Descolada/OCR
- Spawnova ShinsOverlayClass: https://github.com/Spawnova/ShinsOverlayClass
