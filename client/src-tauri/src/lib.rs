/// Read raw file bytes from an absolute path — used by the drag-and-drop
/// handler in the frontend (browser drop events are suppressed by WebView2).
#[tauri::command]
fn read_file_bytes(path: String) -> Result<Vec<u8>, String> {
    std::fs::read(&path).map_err(|e| e.to_string())
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![read_file_bytes])
        .run(tauri::generate_context!())
        .expect("error while running Zync application");
}
