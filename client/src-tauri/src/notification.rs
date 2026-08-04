//! Native Windows toast notifications that report clicks back to the webview.
//!
//! `tauri-plugin-notification` cannot do this. Its Actions API is documented as
//! mobile-only: `register_action_types` exists solely in the plugin's `mobile.rs`,
//! and no desktop code path ever emits the `actionPerformed` event that the JS
//! `onAction` helper subscribes to. The plugin's desktop `show()` also discards
//! the toast handle, so nothing is left to observe. A clicked toast therefore
//! just dismisses — see tauri-apps/plugins-workspace#2150, open since 2022.
//!
//! This module drives WinRT directly to attach an `Activated` handler. The
//! plugin stays in place for macOS and Linux, where clicks remain unsupported
//! upstream and the frontend falls back to it.

use tauri::{AppHandle, Runtime};

/// Event delivered to the webview when the user clicks a toast.
///
/// Carries no payload: the frontend already holds the pending navigation target
/// from when it fired the notification, so re-sending it would just be a second
/// source of truth that could disagree.
pub const ACTIVATED_EVENT: &str = "notification://activated";

/// Show a toast whose click activates the app and notifies the frontend.
#[cfg(windows)]
#[tauri::command]
pub fn show_toast<R: Runtime>(
    app: AppHandle<R>,
    title: String,
    body: String,
    silent: bool,
) -> Result<(), String> {
    windows_impl::show(app, title, body, silent)
}

/// Stub for non-Windows desktops.
///
/// Deliberately fails rather than silently doing nothing, so the frontend can
/// tell "no clickable toast here" apart from "the toast was shown" and fall back
/// to the plugin, which still displays it (inert click).
#[cfg(not(windows))]
#[tauri::command]
pub fn show_toast<R: Runtime>(
    _app: AppHandle<R>,
    _title: String,
    _body: String,
    _silent: bool,
) -> Result<(), String> {
    Err("clickable toasts are implemented for Windows only".into())
}

#[cfg(windows)]
mod windows_impl {
    use super::ACTIVATED_EVENT;
    use std::path::Path;
    use tauri::{AppHandle, Emitter, Manager, Runtime};
    use tauri_winrt_notification::{Duration, Sound, Toast};

    /// Resolve the AppUserModelID to publish the toast under.
    ///
    /// Windows only renders a toast whose AUMID belongs to a registered Start
    /// Menu entry. The installer registers one for the bundle identifier, but a
    /// binary run straight out of `target/` has none, so those borrow
    /// PowerShell's built-in AUMID — the same fallback the upstream plugin uses.
    /// Without it a dev build shows nothing at all, which reads as "the fix
    /// didn't work" when the toast never got as far as being displayed.
    fn app_id<R: Runtime>(app: &AppHandle<R>) -> String {
        let unpackaged = tauri::utils::platform::current_exe()
            .ok()
            .and_then(|exe| exe.parent().map(Path::to_path_buf))
            .map(|dir| dir.ends_with("target\\debug") || dir.ends_with("target\\release"))
            // Unresolvable exe path: assume unpackaged. Showing the toast under
            // PowerShell's identity is cosmetically wrong but still works,
            // whereas an unregistered AUMID shows nothing.
            .unwrap_or(true);

        if unpackaged {
            Toast::POWERSHELL_APP_ID.to_string()
        } else {
            app.config().identifier.clone()
        }
    }

    /// Bring the main window forward — clicking a notification means the user
    /// wants the app, which may be minimised or behind other windows.
    fn focus_main<R: Runtime>(app: &AppHandle<R>) {
        let Some(window) = app.get_webview_window("main") else {
            eprintln!("[notification] no 'main' window to focus");
            return;
        };
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }

    pub fn show<R: Runtime>(
        app: AppHandle<R>,
        title: String,
        body: String,
        silent: bool,
    ) -> Result<(), String> {
        let id = app_id(&app);
        let on_click = app.clone();

        // Built and shown on the main thread on purpose: it owns the STA message
        // pump WebView2 requires, and WinRT dispatches `Activated` through that
        // pump. Off-thread the toast still appears but the click can be lost.
        app.run_on_main_thread(move || {
            let toast = Toast::new(&id)
                .title(&title)
                .text1(&body)
                .duration(Duration::Short)
                // Silent is Do-Not-Disturb: still visible in the Action Center,
                // just without the chime.
                .sound(if silent { None } else { Some(Sound::Default) })
                .on_activated(move |_action| {
                    focus_main(&on_click);
                    let _ = on_click.emit(ACTIVATED_EVENT, ());
                    Ok(())
                });

            if let Err(err) = toast.show() {
                eprintln!("[notification] failed to show toast: {err}");
            }
        })
        .map_err(|err| err.to_string())
    }
}
