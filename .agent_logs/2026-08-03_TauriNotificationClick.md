# Tauri Windows notification click — failed approaches

Symptom: OS notifications fired from the Tauri desktop app appeared correctly, but
clicking one only dismissed it. The same code path in a plain browser worked.
Attempted and abandoned across several sessions before the cause was found.

## Root cause

`tauri-plugin-notification` v2 cannot report desktop notification clicks **at all**.
Verified in the vendored crate source (`tauri-plugin-notification-2.3.3`):

- `register_action_types` is defined only in `src/mobile.rs`. No desktop counterpart.
- `src/lib.rs:224` registers exactly three commands: `notify`, `request_permission`,
  `is_permission_granted`.
- The string `actionPerformed` — the event the JS `onAction()` helper subscribes to —
  appears nowhere in the Rust source. Nothing emits it on desktop.
- `src/desktop.rs:215` fires the toast and drops the handle:
  `tauri::async_runtime::spawn(async move { let _ = notification.show(); });`

Official docs: *"Mobile Only: The Actions API is only available on mobile platforms."*
Upstream feature request: tauri-apps/plugins-workspace#2150, open since March 2022.

## Approaches that DO NOT work — do not retry

1. **`onAction()` from `@tauri-apps/plugin-notification`.** Subscribes to an event no
   desktop code emits. Cannot fire regardless of how it is registered.

2. **`registerActionTypes()` with `foreground: true` buttons.** Invokes
   `plugin:notification|register_action_types`, which is not in the desktop
   `invoke_handler`, so the call rejects. When wrapped in the same `try/catch` as the
   `onAction` registration it also silently skipped attaching the listener — two
   failures masking each other.

3. **Switching between `sendNotification()` and `new window.Notification()`.** These are
   the *same code path*. The plugin injects `init-iife.js`, which replaces
   `window.Notification` with a plain function that invokes
   `plugin:notification|notify` and returns `undefined`. It is not a constructor and
   has no `onclick`, `close()`, or EventTarget behaviour, so assigning `.onclick` is a
   no-op. The JS package's `sendNotification` is literally `new window.Notification(...)`.

4. **Running the packaged `.exe` instead of `tauri dev`.** Changes only the
   AppUserModelID the toast is published under (identifier vs. PowerShell fallback),
   which affects the toast's displayed identity — never click handling.

5. **Frontend-only fixes of any kind.** No amount of JS helps: the event does not exist
   to listen to.

6. **The third-party `tauri-plugin-notifications` fork (Choochmeque).** Advertises
   desktop click support but explicitly does not support Windows yet.

## What worked

A custom `#[tauri::command]` in `client/src-tauri/src/notification.rs` driving
`tauri-winrt-notification` directly to reach `Toast::on_activated`, which the plugin
never exposes. Per Microsoft's WinRT docs the `Activated` event fires for *"apps that
are running"*, so in-process activation needs no COM activator — only a registered
AUMID, which the installer already provides.

Two details that are easy to get wrong:

- **Show the toast on the main thread** (`app.run_on_main_thread`). It owns the STA
  message pump WebView2 requires, and WinRT dispatches `Activated` through that pump.
  Off-thread the toast still appears but the click can be lost — which would look
  exactly like the original bug.
- **Unpackaged builds need `Toast::POWERSHELL_APP_ID`.** Windows renders a toast only
  under an AUMID with a registered Start Menu entry. A binary run out of `target/` has
  none, so it shows *nothing at all* — easily misread as "the fix didn't work".
