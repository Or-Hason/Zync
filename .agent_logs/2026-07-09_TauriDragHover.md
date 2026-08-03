# Failed Approach: Tauri Drag Hover via `listen()` Events

**Date:** 2026-07-09  
**Task:** Fix hover highlight in Tauri desktop app for UploadZone during native file drag.

## What Was Tried

Replaced `getCurrentWindow().onDragDropEvent()` with three separate Tauri event listeners:
- `tauri://file-drop-hover` → setDragging based on getBoundingClientRect check
- `tauri://file-drop-cancelled` → setDragging(false)
- `tauri://file-drop` → file read + handleFile

## Why It Failed

The `tauri://file-drop-hover` / `tauri://file-drop` event names are from an older Tauri 1.x API.
In Tauri 2.x, `onDragDropEvent()` on the window object is the correct API for native file drag handling.
Switching to `listen()` broke the actual file-drop functionality entirely (files could no longer be dropped).

## Correct Approach

- **Native drop handling:** Keep `getCurrentWindow().onDragDropEvent()` for `type === "drop"` and `type === "leave"`.
- **Hover visualization:** Use standard DOM events exclusively — `onDragEnter`, `onDragOver` (with `preventDefault` + `stopPropagation`), `onDragLeave`, `onDrop`. The `stopPropagation()` on `onDragOver` is critical for WebView2 to register the element as a valid drop target.
- **Zone scoping for drop:** `getBoundingClientRect()` position check in the `onDragDropEvent` handler.
