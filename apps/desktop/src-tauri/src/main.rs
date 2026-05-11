#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Deserialize;
use serde_json::Value;
use std::{
    collections::HashMap,
    env, fs,
    io::{self, BufRead, BufReader, Write},
    path::{Path, PathBuf},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{Arc, Mutex as StdMutex},
    time::{Duration, Instant},
};
use tauri::{AppHandle, Emitter, Manager, State};
use tauri_plugin_updater::UpdaterExt;
use tokio::sync::oneshot;
use url::Url;

type PendingMap = Arc<StdMutex<HashMap<String, oneshot::Sender<Result<Value, String>>>>>;
const RPC_TIMEOUT_STANDARD_SECS: u64 = 30;
const RPC_TIMEOUT_LONG_SECS: u64 = 600;
const MAX_SIDECAR_STDOUT_LINE_BYTES: usize = 64 * 1024 * 1024;
const MAX_SIDECAR_STDERR_LINE_BYTES: usize = 1024 * 1024;
const SIDECAR_SHUTDOWN_TIMEOUT_SECS: u64 = 5;

#[derive(Clone)]
struct RunningSidecar {
    child: Arc<StdMutex<Child>>,
    stdin: Arc<StdMutex<ChildStdin>>,
    pending: PendingMap,
}

#[derive(Default)]
struct SidecarRuntime {
    child: Option<RunningSidecar>,
}

impl Drop for SidecarRuntime {
    fn drop(&mut self) {
        if let Some(running) = self.child.take() {
            finish_pending_with_error(&running.pending, "Desktop sidecar owner was dropped.");
            let _ = wait_for_child_exit(&running.child, Duration::from_secs(2));
        }
    }
}

#[derive(Default)]
struct SidecarState {
    runtime: tauri::async_runtime::Mutex<SidecarRuntime>,
}

#[derive(Default)]
struct PendingUpdate(StdMutex<Option<tauri_plugin_updater::Update>>);

fn lock_mutex<T>(mutex: &StdMutex<T>) -> std::sync::MutexGuard<'_, T> {
    mutex
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

#[derive(serde::Serialize)]
struct UpdaterStatus {
    configured: bool,
    endpoint: Option<String>,
    current_version: String,
    pubkey_configured: bool,
}

#[derive(serde::Serialize)]
struct UpdateMetadata {
    version: String,
    current_version: String,
    date: Option<String>,
    body: Option<String>,
}

#[derive(Clone, Default, Deserialize)]
#[serde(default)]
struct ReleaseConfig {
    environment: String,
    cloud_base_url: String,
    updater_endpoint: String,
    updater_public_key: String,
}

struct SidecarLaunchSpec {
    program: PathBuf,
    args: Vec<String>,
    current_dir: Option<PathBuf>,
    envs: Vec<(String, String)>,
    mode: &'static str,
}

fn trim_to_option(value: &str) -> Option<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed.to_string())
    }
}

fn release_config_path(app: &AppHandle) -> Option<PathBuf> {
    let resource_dir = app.path().resource_dir().ok()?;
    let candidate = resource_dir.join("release-config").join("app-config.json");
    if candidate.exists() {
        Some(candidate)
    } else {
        None
    }
}

fn load_release_config(app: &AppHandle) -> ReleaseConfig {
    let mut config = release_config_path(app)
        .and_then(|path| fs::read_to_string(path).ok())
        .and_then(|content| serde_json::from_str::<ReleaseConfig>(&content).ok())
        .unwrap_or_default();

    if let Ok(value) = env::var("DMC_UPDATER_ENDPOINT") {
        if let Some(endpoint) = trim_to_option(&value) {
            config.updater_endpoint = endpoint;
        }
    }
    if let Ok(value) = env::var("DMC_UPDATER_PUBLIC_KEY") {
        if let Some(pubkey) = trim_to_option(&value) {
            config.updater_public_key = pubkey;
        }
    }
    if let Ok(value) = env::var("DMC_CLOUD_BASE_URL") {
        if let Some(base_url) = trim_to_option(&value) {
            config.cloud_base_url = base_url;
        }
    }
    if let Ok(value) = env::var("DMC_RELEASE_ENVIRONMENT") {
        if let Some(environment) = trim_to_option(&value) {
            config.environment = environment;
        }
    }

    config
}

fn configured_cloud_base_url(app: &AppHandle) -> Option<String> {
    let config = load_release_config(app);
    let trimmed = config.cloud_base_url.trim().trim_end_matches('/');
    if trimmed.is_empty() {
        return None;
    }
    Some(trimmed.to_string())
}

fn updater_endpoint(app: &AppHandle) -> Option<String> {
    let config = load_release_config(app);
    if let Some(endpoint) = trim_to_option(&config.updater_endpoint) {
        return Some(endpoint);
    }

    let base_url = configured_cloud_base_url(app)?;
    Some(format!(
        "{base_url}/v1/updates/manifest?current_version={{current_version}}&target={{target}}&arch={{arch}}"
    ))
}

fn updater_pubkey(app: &AppHandle) -> Option<String> {
    trim_to_option(&load_release_config(app).updater_public_key)
}

fn repo_root() -> Result<PathBuf, String> {
    if let Ok(value) = env::var("DMC_REPO_ROOT") {
        let path = PathBuf::from(value);
        if path.exists() {
            return Ok(path);
        }
    }

    let candidate = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(3)
        .map(PathBuf::from)
        .ok_or_else(|| "Could not determine repo root.".to_string())?;

    if candidate.exists() {
        return Ok(candidate);
    }

    Err("Repo root is not available in packaged mode.".to_string())
}

fn combined_python_path(repo_root: &Path) -> Result<String, String> {
    let sidecar_path = repo_root.join("apps").join("sidecar");
    let mut entries = vec![sidecar_path];
    if let Some(existing) = env::var_os("PYTHONPATH") {
        entries.extend(env::split_paths(&existing));
    }
    env::join_paths(entries)
        .map_err(|error| error.to_string())?
        .into_string()
        .map_err(|_| "PYTHONPATH contains unsupported characters.".to_string())
}

fn app_data_sidecar_dir(app: &AppHandle) -> Result<PathBuf, String> {
    app.path()
        .app_data_dir()
        .map(|path| path.join("sidecar"))
        .map_err(|error| error.to_string())
}

fn bundled_sidecar_root(app: &AppHandle) -> Option<PathBuf> {
    if let Ok(value) = env::var("DMC_SIDECAR_BUNDLE_DIR") {
        let path = PathBuf::from(value);
        if path.exists() {
            return Some(path);
        }
    }

    let resource_dir = app.path().resource_dir().ok()?;
    let candidate = resource_dir.join("bundled-sidecar");
    if candidate.exists() {
        return Some(candidate);
    }
    None
}

fn bundled_sidecar_launch_spec(app: &AppHandle) -> Result<Option<SidecarLaunchSpec>, String> {
    let sidecar_root = match bundled_sidecar_root(app) {
        Some(path) => path,
        None => return Ok(None),
    };

    let explicit_exe = env::var("DMC_SIDECAR_EXE")
        .ok()
        .map(PathBuf::from)
        .filter(|path| path.exists());
    let program = explicit_exe.unwrap_or_else(|| sidecar_root.join("dmc-sidecar.exe"));
    if !program.exists() {
        return Ok(None);
    }

    let data_dir = app_data_sidecar_dir(app)?;
    let browser_dir = data_dir.join("ms-playwright");
    let resources_dir = sidecar_root.join("sidecar-resources");
    let mut envs = vec![
        (
            "DMC_DATA_DIR".to_string(),
            data_dir.to_string_lossy().to_string(),
        ),
        (
            "PLAYWRIGHT_BROWSERS_PATH".to_string(),
            browser_dir.to_string_lossy().to_string(),
        ),
    ];
    if resources_dir.exists() {
        envs.push((
            "DMC_BUNDLED_RESOURCES_DIR".to_string(),
            resources_dir.to_string_lossy().to_string(),
        ));
    }
    if let Some(cloud_base_url) = configured_cloud_base_url(app) {
        envs.push(("DMC_CLOUD_BASE_URL".to_string(), cloud_base_url));
    }
    Ok(Some(SidecarLaunchSpec {
        program,
        args: Vec::new(),
        current_dir: Some(sidecar_root),
        envs,
        mode: "bundled",
    }))
}

fn python_sidecar_launch_specs(app: &AppHandle) -> Result<Vec<SidecarLaunchSpec>, String> {
    let repo_root = repo_root()?;
    let python_path = combined_python_path(&repo_root)?;
    let data_dir = app_data_sidecar_dir(app)?;
    let browser_dir = data_dir.join("ms-playwright");
    let mut shared_envs = vec![
        ("PYTHONPATH".to_string(), python_path),
        (
            "DMC_REPO_ROOT".to_string(),
            repo_root.to_string_lossy().to_string(),
        ),
        (
            "DMC_DATA_DIR".to_string(),
            data_dir.to_string_lossy().to_string(),
        ),
        (
            "PLAYWRIGHT_BROWSERS_PATH".to_string(),
            browser_dir.to_string_lossy().to_string(),
        ),
    ];
    if let Some(cloud_base_url) = configured_cloud_base_url(app) {
        shared_envs.push(("DMC_CLOUD_BASE_URL".to_string(), cloud_base_url));
    }
    let program_candidates: Vec<(String, Vec<String>)> = match env::var("DMC_PYTHON") {
        Ok(custom) => vec![
            (custom, vec!["-m".to_string(), "dmc_sidecar".to_string()]),
            (
                "python".to_string(),
                vec!["-m".to_string(), "dmc_sidecar".to_string()],
            ),
            (
                "py".to_string(),
                vec![
                    "-3".to_string(),
                    "-m".to_string(),
                    "dmc_sidecar".to_string(),
                ],
            ),
        ],
        Err(_) => vec![
            (
                "python".to_string(),
                vec!["-m".to_string(), "dmc_sidecar".to_string()],
            ),
            (
                "py".to_string(),
                vec![
                    "-3".to_string(),
                    "-m".to_string(),
                    "dmc_sidecar".to_string(),
                ],
            ),
        ],
    };

    Ok(program_candidates
        .into_iter()
        .map(|(program, args)| SidecarLaunchSpec {
            program: PathBuf::from(program),
            args,
            current_dir: Some(repo_root.clone()),
            envs: shared_envs.clone(),
            mode: "python",
        })
        .collect())
}

fn finish_pending_with_error(pending: &PendingMap, message: &str) {
    let pending_senders = {
        let mut guard = lock_mutex(pending);
        guard.drain().map(|(_, sender)| sender).collect::<Vec<_>>()
    };
    for sender in pending_senders {
        let _ = sender.send(Err(message.to_string()));
    }
}

fn read_limited_line<R: BufRead>(reader: &mut R, limit: usize) -> io::Result<Option<String>> {
    let mut buffer = Vec::new();
    loop {
        let available = reader.fill_buf()?;
        if available.is_empty() {
            if buffer.is_empty() {
                return Ok(None);
            }
            break;
        }

        let newline_index = available.iter().position(|byte| *byte == b'\n');
        let take_len = newline_index.map_or(available.len(), |index| index + 1);
        if buffer.len() + take_len > limit {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                format!("Sidecar output line exceeded {limit} bytes."),
            ));
        }

        buffer.extend_from_slice(&available[..take_len]);
        reader.consume(take_len);
        if newline_index.is_some() {
            break;
        }
    }

    if buffer.last().is_some_and(|byte| *byte == b'\n') {
        buffer.pop();
    }
    if buffer.last().is_some_and(|byte| *byte == b'\r') {
        buffer.pop();
    }

    String::from_utf8(buffer)
        .map(Some)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))
}

fn sidecar_exit_code(child: &Arc<StdMutex<Child>>) -> Option<i32> {
    let mut child_guard = lock_mutex(child);
    child_guard
        .try_wait()
        .ok()
        .flatten()
        .and_then(|status| status.code())
}

fn clear_runtime_if_child(app: AppHandle, expected_child: Arc<StdMutex<Child>>) {
    tauri::async_runtime::spawn(async move {
        let state = app.state::<SidecarState>();
        let mut runtime = state.runtime.lock().await;
        let should_clear = runtime
            .child
            .as_ref()
            .is_some_and(|current| Arc::ptr_eq(&current.child, &expected_child));
        if should_clear {
            runtime.child = None;
        }
    });
}

async fn clear_runtime_if_child_now(
    state: &State<'_, SidecarState>,
    expected_child: &Arc<StdMutex<Child>>,
) {
    let mut runtime = state.runtime.lock().await;
    let should_clear = runtime
        .child
        .as_ref()
        .is_some_and(|current| Arc::ptr_eq(&current.child, expected_child));
    if should_clear {
        runtime.child = None;
    }
}

fn wait_for_child_exit(
    child: &Arc<StdMutex<Child>>,
    timeout: Duration,
) -> Result<Option<i32>, String> {
    let mut child_guard = lock_mutex(child);
    if let Some(status) = child_guard.try_wait().map_err(|error| error.to_string())? {
        return Ok(status.code());
    }

    let _ = child_guard.kill();
    let deadline = Instant::now() + timeout;
    loop {
        if let Some(status) = child_guard.try_wait().map_err(|error| error.to_string())? {
            return Ok(status.code());
        }
        if Instant::now() >= deadline {
            return Err("Timed out waiting for sidecar process to exit.".to_string());
        }
        std::thread::sleep(Duration::from_millis(50));
    }
}

fn write_sidecar_request(running: &RunningSidecar, request_json: &str) -> Result<(), String> {
    let mut stdin = lock_mutex(&running.stdin);
    stdin
        .write_all(request_json.as_bytes())
        .map_err(|error| format!("Failed writing to sidecar stdin: {error}"))?;
    stdin
        .write_all(b"\n")
        .map_err(|error| format!("Failed writing request terminator to sidecar stdin: {error}"))?;
    stdin
        .flush()
        .map_err(|error| format!("Failed flushing sidecar stdin: {error}"))
}

fn spawn_sidecar_process(app: &AppHandle) -> Result<RunningSidecar, String> {
    let mut launch_specs = Vec::new();
    let bundled_spec = bundled_sidecar_launch_spec(app)?;
    let python_specs = python_sidecar_launch_specs(app).unwrap_or_default();

    if cfg!(debug_assertions) {
        launch_specs.extend(python_specs);
        if let Some(spec) = bundled_spec {
            launch_specs.push(spec);
        }
    } else {
        if let Some(spec) = bundled_spec {
            launch_specs.push(spec);
        }
        launch_specs.extend(python_specs);
    }

    let mut last_error = String::from("No sidecar runtime candidate succeeded.");

    for spec in launch_specs {
        let mut command = Command::new(&spec.program);
        command
            .args(&spec.args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        if let Some(current_dir) = &spec.current_dir {
            command.current_dir(current_dir);
        }
        for (key, value) in &spec.envs {
            command.env(key, value);
        }

        let mut child = match command.spawn() {
            Ok(child) => child,
            Err(error) => {
                last_error = format!("{} [{}]: {error}", spec.program.display(), spec.mode);
                continue;
            }
        };

        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "Could not capture sidecar stdout.".to_string())?;
        let stderr = child
            .stderr
            .take()
            .ok_or_else(|| "Could not capture sidecar stderr.".to_string())?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| "Could not capture sidecar stdin.".to_string())?;

        let pending: PendingMap = Arc::new(StdMutex::new(HashMap::new()));
        let running = RunningSidecar {
            child: Arc::new(StdMutex::new(child)),
            stdin: Arc::new(StdMutex::new(stdin)),
            pending,
        };

        let app_for_stdout = app.clone();
        let pending_for_stdout = Arc::clone(&running.pending);
        let child_for_stdout = Arc::clone(&running.child);
        std::thread::spawn(move || {
            let mut reader = BufReader::new(stdout);
            loop {
                match read_limited_line(&mut reader, MAX_SIDECAR_STDOUT_LINE_BYTES) {
                    Ok(Some(line)) => {
                        let trimmed = line.trim();
                        if trimmed.is_empty() {
                            continue;
                        }

                        match serde_json::from_str::<Value>(trimmed) {
                            Ok(payload) => {
                                if payload
                                    .get("method")
                                    .and_then(Value::as_str)
                                    .is_some_and(|method| method == "event")
                                {
                                    if let Some(params) = payload.get("params") {
                                        let _ =
                                            app_for_stdout.emit("sidecar-event", params.clone());
                                    }
                                    continue;
                                }

                                let response_id = payload.get("id").map(|value| match value {
                                    Value::String(text) => text.clone(),
                                    Value::Number(number) => number.to_string(),
                                    _ => String::new(),
                                });

                                if let Some(request_id) = response_id {
                                    if !request_id.is_empty() {
                                        if let Some(sender) =
                                            lock_mutex(&pending_for_stdout).remove(&request_id)
                                        {
                                            let _ = sender.send(Ok(payload));
                                        }
                                    }
                                }
                            }
                            Err(error) => {
                                let _ = app_for_stdout.emit(
                                    "sidecar-event",
                                    serde_json::json!({
                                        "type": "sidecar_stderr",
                                        "message": format!("Invalid sidecar stdout JSON: {error}"),
                                    }),
                                );
                            }
                        }
                    }
                    Ok(None) => break,
                    Err(error) => {
                        let _ = app_for_stdout.emit(
                            "sidecar-event",
                            serde_json::json!({
                                "type": "sidecar_stderr",
                                "message": format!("Failed reading sidecar stdout: {error}"),
                            }),
                        );
                        break;
                    }
                }
            }

            finish_pending_with_error(
                &pending_for_stdout,
                "Sidecar stdout closed before a response was received.",
            );
            let exit_code = sidecar_exit_code(&child_for_stdout);
            let _ = app_for_stdout.emit(
                "sidecar-event",
                serde_json::json!({
                    "type": "sidecar_exited",
                    "code": exit_code,
                    "signal": Option::<String>::None,
                }),
            );
            clear_runtime_if_child(app_for_stdout, child_for_stdout);
        });

        let app_for_stderr = app.clone();
        std::thread::spawn(move || {
            let mut reader = BufReader::new(stderr);
            loop {
                match read_limited_line(&mut reader, MAX_SIDECAR_STDERR_LINE_BYTES) {
                    Ok(Some(line)) => {
                        let trimmed = line.trim();
                        if trimmed.is_empty() {
                            continue;
                        }
                        let _ = app_for_stderr.emit(
                            "sidecar-event",
                            serde_json::json!({
                                "type": "sidecar_stderr",
                                "message": trimmed,
                            }),
                        );
                    }
                    Ok(None) => break,
                    Err(error) => {
                        let _ = app_for_stderr.emit(
                            "sidecar-event",
                            serde_json::json!({
                                "type": "sidecar_stderr",
                                "message": format!("Failed reading sidecar stderr: {error}"),
                            }),
                        );
                        break;
                    }
                }
            }
        });

        let pid = lock_mutex(&running.child).id();
        let _ = app.emit(
            "sidecar-event",
            serde_json::json!({
                "type": "sidecar_started",
                "pid": pid,
                "mode": spec.mode,
                "program": spec.program,
            }),
        );

        return Ok(running);
    }

    Err(format!(
        "Could not start sidecar. {last_error}. For packaged builds, run `pnpm run sidecar:bundle` before `pnpm run desktop:package`."
    ))
}

async fn ensure_sidecar_running(
    app: &AppHandle,
    state: &State<'_, SidecarState>,
) -> Result<RunningSidecar, String> {
    let mut runtime = state.runtime.lock().await;

    if let Some(existing) = runtime.child.clone() {
        let is_running = {
            let mut child = lock_mutex(&existing.child);
            child
                .try_wait()
                .map_err(|error| error.to_string())?
                .is_none()
        };

        if is_running {
            return Ok(existing);
        }

        runtime.child = None;
    }

    let spawned = spawn_sidecar_process(app)?;
    runtime.child = Some(spawned.clone());
    Ok(spawned)
}

fn extract_request_id(request_json: &str) -> Result<String, String> {
    let payload: Value = serde_json::from_str(request_json).map_err(|error| error.to_string())?;
    let id_value = payload
        .get("id")
        .ok_or_else(|| "JSON-RPC request must include an id.".to_string())?;

    match id_value {
        Value::String(text) => Ok(text.clone()),
        Value::Number(number) => Ok(number.to_string()),
        _ => Err("JSON-RPC request id must be a string or number.".to_string()),
    }
}

fn extract_request_method(request_json: &str) -> Result<String, String> {
    let payload: Value = serde_json::from_str(request_json).map_err(|error| error.to_string())?;
    payload
        .get("method")
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or_else(|| "JSON-RPC request must include a string method.".to_string())
}

fn rpc_timeout_secs(method: &str) -> u64 {
    match method {
        "ping" => RPC_TIMEOUT_STANDARD_SECS,
        "start_job"
        | "resume_existing_job"
        | "install_browser_runtime"
        | "export_student_basic_info_form"
        | "validate_current_student_sources"
        | "export_current_student_import_excel"
        | "preview_dmc_form_json"
        | "export_dmc_form_json"
        | "ocr_dmc_form_with_akson" => RPC_TIMEOUT_LONG_SECS,
        _ => RPC_TIMEOUT_STANDARD_SECS,
    }
}

#[cfg(test)]
mod rpc_timeout_tests {
    use super::{rpc_timeout_secs, RPC_TIMEOUT_LONG_SECS, RPC_TIMEOUT_STANDARD_SECS};

    #[test]
    fn form_converter_rpc_methods_use_long_timeout() {
        for method in [
            "validate_current_student_sources",
            "export_current_student_import_excel",
            "preview_dmc_form_json",
            "export_dmc_form_json",
            "ocr_dmc_form_with_akson",
        ] {
            assert_eq!(rpc_timeout_secs(method), RPC_TIMEOUT_LONG_SECS);
        }
    }

    #[test]
    fn lightweight_rpc_methods_keep_standard_timeout() {
        assert_eq!(rpc_timeout_secs("ping"), RPC_TIMEOUT_STANDARD_SECS);
        assert_eq!(
            rpc_timeout_secs("get_account_status"),
            RPC_TIMEOUT_STANDARD_SECS
        );
    }
}

async fn perform_rpc_request(
    app: &AppHandle,
    state: &State<'_, SidecarState>,
    request_json: String,
) -> Result<Value, String> {
    let request_id = extract_request_id(&request_json)?;
    let method = extract_request_method(&request_json)?;
    let timeout_secs = rpc_timeout_secs(&method);
    let mut last_write_error = None;

    for attempt in 0..2 {
        let running = ensure_sidecar_running(app, state).await?;
        let (sender, receiver) = oneshot::channel::<Result<Value, String>>();
        {
            let mut pending = lock_mutex(&running.pending);
            pending.insert(request_id.clone(), sender);
        }

        if let Err(error) = write_sidecar_request(&running, &request_json) {
            lock_mutex(&running.pending).remove(&request_id);
            finish_pending_with_error(
                &running.pending,
                "Sidecar stdin closed while writing a request.",
            );
            clear_runtime_if_child_now(state, &running.child).await;
            let child_for_shutdown = Arc::clone(&running.child);
            let _ = tauri::async_runtime::spawn_blocking(move || {
                wait_for_child_exit(&child_for_shutdown, Duration::from_secs(1))
            })
            .await;
            last_write_error = Some(error);
            if attempt == 0 {
                continue;
            }
            return Err(
                last_write_error.unwrap_or_else(|| "Failed writing to sidecar stdin.".to_string())
            );
        }

        let response = match tokio::time::timeout(Duration::from_secs(timeout_secs), receiver).await
        {
            Ok(Ok(result)) => result?,
            Ok(Err(_)) => return Err("Sidecar response channel closed unexpectedly.".to_string()),
            Err(_) => {
                lock_mutex(&running.pending).remove(&request_id);
                return Err("Timed out waiting for sidecar response.".to_string());
            }
        };

        if let Some(error) = response.get("error") {
            let code = error
                .get("code")
                .and_then(Value::as_str)
                .unwrap_or("UNKNOWN_ERROR");
            let message = error
                .get("message")
                .and_then(Value::as_str)
                .unwrap_or("Unknown JSON-RPC error.");
            return Err(format!("{code}: {message}"));
        }

        return response
            .get("result")
            .cloned()
            .ok_or_else(|| "JSON-RPC response is missing the result field.".to_string());
    }

    Err(last_write_error.unwrap_or_else(|| "Failed writing to sidecar stdin.".to_string()))
}

fn current_app_version(app: &AppHandle) -> String {
    app.package_info().version.to_string()
}

fn build_updater_status(app: &AppHandle) -> UpdaterStatus {
    let endpoint = updater_endpoint(app);
    let pubkey = updater_pubkey(app);
    UpdaterStatus {
        configured: endpoint.is_some() && pubkey.is_some(),
        endpoint,
        current_version: current_app_version(app),
        pubkey_configured: pubkey.is_some(),
    }
}

fn build_runtime_updater(app: &AppHandle) -> Result<tauri_plugin_updater::UpdaterBuilder, String> {
    let endpoint = updater_endpoint(app).ok_or_else(|| "UPDATER_NOT_CONFIGURED".to_string())?;
    let pubkey = updater_pubkey(app).ok_or_else(|| "UPDATER_NOT_CONFIGURED".to_string())?;
    let url =
        Url::parse(&endpoint).map_err(|error| format!("UPDATER_ENDPOINT_INVALID: {error}"))?;
    app.updater_builder()
        .pubkey(pubkey)
        .endpoints(vec![url])
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn initialize_sidecar(
    app: AppHandle,
    state: State<'_, SidecarState>,
) -> Result<Value, String> {
    ensure_sidecar_running(&app, &state).await?;
    let request_id = format!(
        "desktop-ping-{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_err(|error| error.to_string())?
            .as_millis()
    );
    perform_rpc_request(
        &app,
        &state,
        serde_json::json!({
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "ping",
            "params": {},
        })
        .to_string(),
    )
    .await
}

#[tauri::command]
async fn rpc_request(
    app: AppHandle,
    state: State<'_, SidecarState>,
    request_json: String,
) -> Result<Value, String> {
    perform_rpc_request(&app, &state, request_json).await
}

#[tauri::command]
async fn shutdown_sidecar(app: AppHandle, state: State<'_, SidecarState>) -> Result<(), String> {
    let running = {
        let mut runtime = state.runtime.lock().await;
        runtime.child.take()
    };

    if let Some(running) = running {
        finish_pending_with_error(&running.pending, "Sidecar shut down by desktop.");
        let child = Arc::clone(&running.child);
        let exit_code = tauri::async_runtime::spawn_blocking(move || {
            wait_for_child_exit(&child, Duration::from_secs(SIDECAR_SHUTDOWN_TIMEOUT_SECS))
        })
        .await
        .map_err(|error| error.to_string())??;
        let _ = app.emit(
            "sidecar-event",
            serde_json::json!({
                "type": "sidecar_exited",
                "code": exit_code,
                "signal": Option::<String>::None,
            }),
        );
    }

    Ok(())
}

#[tauri::command]
fn open_excel_dialog() -> Option<String> {
    rfd::FileDialog::new()
        .add_filter("Excel", &["xlsx", "xlsm", "xls"])
        .pick_file()
        .map(|path| path.to_string_lossy().to_string())
}

#[tauri::command]
fn open_csv_dialog() -> Option<String> {
    rfd::FileDialog::new()
        .add_filter("CSV", &["csv"])
        .pick_file()
        .map(|path| path.to_string_lossy().to_string())
}

#[tauri::command]
fn open_markdown_dialog() -> Option<String> {
    rfd::FileDialog::new()
        .add_filter("Markdown/Text/CSV", &["md", "txt", "csv"])
        .pick_file()
        .map(|path| path.to_string_lossy().to_string())
}

#[tauri::command]
fn open_ocr_source_dialog() -> Option<String> {
    rfd::FileDialog::new()
        .add_filter("OCR Source", &["pdf", "png", "jpg", "jpeg", "webp"])
        .pick_file()
        .map(|path| path.to_string_lossy().to_string())
}

#[tauri::command]
fn open_evidence_dialog() -> Option<String> {
    rfd::FileDialog::new()
        .add_filter(
            "Evidence",
            &["pdf", "docx", "xlsx", "xlsm", "xls", "png", "jpg", "jpeg"],
        )
        .pick_file()
        .map(|path| path.to_string_lossy().to_string())
}

#[tauri::command]
fn open_backup_archive_dialog() -> Option<String> {
    rfd::FileDialog::new()
        .add_filter("Backup Archive", &["zip"])
        .pick_file()
        .map(|path| path.to_string_lossy().to_string())
}

#[tauri::command]
fn save_backup_dialog(default_name: Option<String>) -> Option<String> {
    let mut dialog = rfd::FileDialog::new().add_filter("Backup Archive", &["zip"]);
    if let Some(name) = default_name.as_deref() {
        dialog = dialog.set_file_name(name);
    }
    dialog
        .save_file()
        .map(|path| path.to_string_lossy().to_string())
}

#[tauri::command]
fn save_diagnostics_dialog(default_name: Option<String>) -> Option<String> {
    let mut dialog = rfd::FileDialog::new().add_filter("JSON", &["json"]);
    if let Some(name) = default_name.as_deref() {
        dialog = dialog.set_file_name(name);
    }
    dialog
        .save_file()
        .map(|path| path.to_string_lossy().to_string())
}

fn template_source_path(app: &AppHandle) -> Result<PathBuf, String> {
    if let Ok(resource_dir) = app.path().resource_dir() {
        let candidate = resource_dir.join("templates").join("obec-study-form.xlsx");
        if candidate.exists() {
            return Ok(candidate);
        }
    }

    let candidate = repo_root()?.join("obec-study-form.xlsx");
    if candidate.exists() {
        return Ok(candidate);
    }

    Err("TEMPLATE_NOT_FOUND".to_string())
}

#[tauri::command]
fn save_template_dialog(default_name: Option<String>) -> Option<String> {
    let mut dialog = rfd::FileDialog::new().add_filter("Excel", &["xlsx"]);
    if let Some(name) = default_name.as_deref() {
        dialog = dialog.set_file_name(name);
    }
    dialog
        .save_file()
        .map(|path| path.to_string_lossy().to_string())
}

#[tauri::command]
fn copy_template_file(app: AppHandle, destination_path: String) -> Result<String, String> {
    let source = template_source_path(&app)?;
    let target = PathBuf::from(destination_path);
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    fs::copy(source, &target).map_err(|error| error.to_string())?;
    Ok(target.to_string_lossy().to_string())
}

#[tauri::command]
fn write_text_file(path: String, contents: String) -> Result<(), String> {
    let target = PathBuf::from(path);
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    fs::write(target, contents).map_err(|error| error.to_string())
}

#[tauri::command]
fn reveal_path(path: String) -> Result<(), String> {
    let target = PathBuf::from(path);
    if !target.exists() {
        return Err("PATH_NOT_FOUND".to_string());
    }

    #[cfg(target_os = "windows")]
    {
        if target.is_file() {
            Command::new("explorer")
                .arg(format!("/select,{}", target.to_string_lossy()))
                .spawn()
                .map_err(|error| error.to_string())?;
        } else {
            Command::new("explorer")
                .arg(target.to_string_lossy().to_string())
                .spawn()
                .map_err(|error| error.to_string())?;
        }
    }

    #[cfg(not(target_os = "windows"))]
    {
        let open_target = if target.is_file() {
            target.parent().unwrap_or(&target).to_path_buf()
        } else {
            target
        };
        Command::new("xdg-open")
            .arg(open_target)
            .spawn()
            .map_err(|error| error.to_string())?;
    }

    Ok(())
}

#[tauri::command]
fn get_updater_status(app: AppHandle) -> UpdaterStatus {
    build_updater_status(&app)
}

#[tauri::command]
async fn check_for_app_update(
    app: AppHandle,
    pending_update: State<'_, PendingUpdate>,
) -> Result<Value, String> {
    let update = build_runtime_updater(&app)?
        .build()
        .map_err(|error| error.to_string())?
        .check()
        .await
        .map_err(|error| error.to_string())?;

    let metadata = update.as_ref().map(|item| UpdateMetadata {
        version: item.version.clone(),
        current_version: item.current_version.clone(),
        date: item.date.map(|value| value.to_string()),
        body: item.body.clone(),
    });

    *lock_mutex(&pending_update.0) = update;
    serde_json::to_value(metadata).map_err(|error| error.to_string())
}

#[tauri::command]
async fn install_app_update(
    app: AppHandle,
    pending_update: State<'_, PendingUpdate>,
) -> Result<(), String> {
    let update = lock_mutex(&pending_update.0)
        .take()
        .ok_or_else(|| "NO_PENDING_UPDATE".to_string())?;

    let app_for_progress = app.clone();
    let mut downloaded: u64 = 0;
    update
        .download_and_install(
            move |chunk_length, content_length| {
                downloaded += chunk_length as u64;
                let event_type = if downloaded == chunk_length as u64 {
                    "started"
                } else {
                    "progress"
                };
                let _ = app_for_progress.emit(
                    "updater-event",
                    serde_json::json!({
                        "type": event_type,
                        "downloaded": downloaded,
                        "contentLength": content_length,
                    }),
                );
            },
            {
                let app_for_finish = app.clone();
                move || {
                    let _ = app_for_finish.emit(
                        "updater-event",
                        serde_json::json!({
                            "type": "finished",
                        }),
                    );
                }
            },
        )
        .await
        .map_err(|error| {
            let message = error.to_string();
            let _ = app.emit(
                "updater-event",
                serde_json::json!({
                    "type": "error",
                    "message": message,
                }),
            );
            message
        })?;

    let _ = app.emit(
        "updater-event",
        serde_json::json!({
            "type": "installed",
        }),
    );
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(SidecarState::default())
        .manage(PendingUpdate::default())
        .invoke_handler(tauri::generate_handler![
            initialize_sidecar,
            rpc_request,
            shutdown_sidecar,
            open_excel_dialog,
            open_csv_dialog,
            open_markdown_dialog,
            open_ocr_source_dialog,
            open_evidence_dialog,
            open_backup_archive_dialog,
            save_backup_dialog,
            save_diagnostics_dialog,
            save_template_dialog,
            copy_template_file,
            write_text_file,
            reveal_path,
            get_updater_status,
            check_for_app_update,
            install_app_update
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::{UpdateMetadata, UpdaterStatus};

    #[test]
    fn updater_status_serializes_with_frontend_contract_keys() {
        let value = serde_json::to_value(UpdaterStatus {
            configured: false,
            endpoint: None,
            current_version: "0.1.0".to_string(),
            pubkey_configured: false,
        })
        .expect("updater status should serialize");

        assert_eq!(value["current_version"], "0.1.0");
        assert_eq!(value["pubkey_configured"], false);
        assert!(value.get("currentVersion").is_none());
        assert!(value.get("pubkeyConfigured").is_none());
    }

    #[test]
    fn update_metadata_serializes_with_frontend_contract_keys() {
        let value = serde_json::to_value(UpdateMetadata {
            version: "0.2.0".to_string(),
            current_version: "0.1.0".to_string(),
            date: None,
            body: None,
        })
        .expect("update metadata should serialize");

        assert_eq!(value["current_version"], "0.1.0");
        assert!(value.get("currentVersion").is_none());
    }
}
