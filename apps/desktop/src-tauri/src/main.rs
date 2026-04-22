#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde_json::Value;
use std::{
    collections::HashMap,
    env,
    io::{BufRead, BufReader, Write},
    path::PathBuf,
    process::{Child, ChildStdin, Command, Stdio},
    sync::{Arc, Mutex as StdMutex},
    time::Duration,
};
use tauri::{AppHandle, Emitter, State};
use tokio::sync::oneshot;

type PendingMap = Arc<StdMutex<HashMap<String, oneshot::Sender<Result<Value, String>>>>>;

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

#[derive(Default)]
struct SidecarState {
    runtime: tauri::async_runtime::Mutex<SidecarRuntime>,
}

fn repo_root() -> Result<PathBuf, String> {
    if let Ok(value) = env::var("DMC_REPO_ROOT") {
        return Ok(PathBuf::from(value));
    }

    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(3)
        .map(PathBuf::from)
        .ok_or_else(|| "Could not determine repo root.".to_string())
}

fn combined_python_path(repo_root: &PathBuf) -> Result<String, String> {
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

fn finish_pending_with_error(pending: &PendingMap, message: &str) {
    let pending_senders = {
        let mut guard = pending.lock().expect("pending map poisoned");
        guard.drain().map(|(_, sender)| sender).collect::<Vec<_>>()
    };
    for sender in pending_senders {
        let _ = sender.send(Err(message.to_string()));
    }
}

fn spawn_sidecar_process(app: &AppHandle) -> Result<RunningSidecar, String> {
    let repo_root = repo_root()?;
    let python_path = combined_python_path(&repo_root)?;
    let program_candidates: Vec<(String, Vec<&str>)> = match env::var("DMC_PYTHON") {
        Ok(custom) => vec![
            (custom, vec!["-m", "dmc_sidecar"]),
            ("python".to_string(), vec!["-m", "dmc_sidecar"]),
            ("py".to_string(), vec!["-3", "-m", "dmc_sidecar"]),
        ],
        Err(_) => vec![
            ("python".to_string(), vec!["-m", "dmc_sidecar"]),
            ("py".to_string(), vec!["-3", "-m", "dmc_sidecar"]),
        ],
    };

    let mut last_error = String::from("No Python runtime candidate succeeded.");

    for (program, args) in program_candidates {
        let mut command = Command::new(&program);
        command
            .args(args)
            .current_dir(&repo_root)
            .env("PYTHONPATH", &python_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        let mut child = match command.spawn() {
            Ok(child) => child,
            Err(error) => {
                last_error = format!("{program}: {error}");
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
        let app_for_stdout = app.clone();
        let pending_for_stdout = Arc::clone(&pending);
        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line_result in reader.lines() {
                match line_result {
                    Ok(line) => {
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
                                        let _ = app_for_stdout.emit("sidecar-event", params.clone());
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
                                        if let Some(sender) = pending_for_stdout
                                            .lock()
                                            .expect("pending map poisoned")
                                            .remove(&request_id)
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
        });

        let app_for_stderr = app.clone();
        std::thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines().map_while(Result::ok) {
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
        });

        let running = RunningSidecar {
            child: Arc::new(StdMutex::new(child)),
            stdin: Arc::new(StdMutex::new(stdin)),
            pending,
        };

        let pid = running
            .child
            .lock()
            .expect("child process mutex poisoned")
            .id();
        let _ = app.emit(
            "sidecar-event",
            serde_json::json!({
                "type": "sidecar_started",
                "pid": pid,
            }),
        );

        return Ok(running);
    }

    Err(format!("Could not start sidecar. {last_error}"))
}

async fn ensure_sidecar_running(
    app: &AppHandle,
    state: &State<'_, SidecarState>,
) -> Result<RunningSidecar, String> {
    let mut runtime = state.runtime.lock().await;

    if let Some(existing) = runtime.child.clone() {
        let is_running = {
            let mut child = existing.child.lock().expect("child process mutex poisoned");
            child.try_wait().map_err(|error| error.to_string())?.is_none()
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

async fn perform_rpc_request(
    app: &AppHandle,
    state: &State<'_, SidecarState>,
    request_json: String,
) -> Result<Value, String> {
    let request_id = extract_request_id(&request_json)?;
    let running = ensure_sidecar_running(app, state).await?;

    let (sender, receiver) = oneshot::channel::<Result<Value, String>>();
    {
        let mut pending = running.pending.lock().expect("pending map poisoned");
        pending.insert(request_id.clone(), sender);
    }

    {
        let mut stdin = running.stdin.lock().expect("sidecar stdin mutex poisoned");
        if let Err(error) = stdin.write_all(request_json.as_bytes()) {
            running
                .pending
                .lock()
                .expect("pending map poisoned")
                .remove(&request_id);
            return Err(format!("Failed writing to sidecar stdin: {error}"));
        }
        if let Err(error) = stdin.write_all(b"\n") {
            running
                .pending
                .lock()
                .expect("pending map poisoned")
                .remove(&request_id);
            return Err(format!("Failed writing request terminator to sidecar stdin: {error}"));
        }
        if let Err(error) = stdin.flush() {
            running
                .pending
                .lock()
                .expect("pending map poisoned")
                .remove(&request_id);
            return Err(format!("Failed flushing sidecar stdin: {error}"));
        }
    }

    let response = tokio::time::timeout(Duration::from_secs(180), receiver)
        .await
        .map_err(|_| "Timed out waiting for sidecar response.".to_string())?
        .map_err(|_| "Sidecar response channel closed unexpectedly.".to_string())??;

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

    response
        .get("result")
        .cloned()
        .ok_or_else(|| "JSON-RPC response is missing the result field.".to_string())
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
async fn shutdown_sidecar(
    app: AppHandle,
    state: State<'_, SidecarState>,
) -> Result<(), String> {
    let running = {
        let mut runtime = state.runtime.lock().await;
        runtime.child.take()
    };

    if let Some(running) = running {
        finish_pending_with_error(&running.pending, "Sidecar shut down by desktop.");
        let mut child = running.child.lock().expect("child process mutex poisoned");
        let _ = child.kill();
        let status = child.wait().map_err(|error| error.to_string())?;
        let _ = app.emit(
            "sidecar-event",
            serde_json::json!({
                "type": "sidecar_exited",
                "code": status.code(),
                "signal": Option::<String>::None,
            }),
        );
    }

    Ok(())
}

fn main() {
    tauri::Builder::default()
        .manage(SidecarState::default())
        .invoke_handler(tauri::generate_handler![
            initialize_sidecar,
            rpc_request,
            shutdown_sidecar
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
