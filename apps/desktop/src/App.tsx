import { useCallback, useEffect, useMemo, useState } from "react";
import messages from "./i18n/th.json";
import {
  activateLicense,
  bootstrapBrowserRuntime,
  checkForAppUpdate,
  copyTemplateFile,
  createBackup,
  getBrowserRuntimeStatus,
  getDatabaseStatus,
  getLicenseStatus,
  getModuleConfigStatus,
  getUpdaterStatus,
  initializeSidecar,
  installAppUpdate,
  listJobs,
  listenSidecarEvents,
  listenUpdaterEvents,
  openBackupArchiveDialog,
  openExcelDialog,
  refreshLicenseStatus,
  restoreBackup,
  revealPath,
  saveBackupDialog,
  saveDiagnosticsDialog,
  saveTemplateDialog,
  startGraduationJob,
  syncModuleConfig,
  validateExcel,
  writeTextFile,
  pauseJob,
  resumeExistingJob,
  resumeJob,
  cancelJob,
  getJobStatus,
} from "./lib/rpcClient";
import { buildDraftJob, buildJobId, buildSupportDiagnostics, buildTimestampSlug } from "./lib/appUi";
import { useJobStatusReconciliation } from "./hooks/useJobStatusReconciliation";
import { usePeriodicLicenseHeartbeat } from "./hooks/usePeriodicLicenseHeartbeat";
import { useJobStore } from "./stores/useJobStore";
import { GraduationWizard } from "./components/GraduationWizard";
import { ModuleHome } from "./components/ModuleHome";
import type {
  AvailableUpdate,
  BrowserRuntimeStatus,
  DatabaseStatus,
  JobStatusSnapshot,
  LicenseStatus,
  UpdaterStatus,
} from "./types/contracts";

export function App() {
  const {
    preview,
    currentJob,
    licenseStatus,
    moduleConfigStatus,
    existingJobs,
    excelPath,
    connectionState,
    isValidating,
    isStartingJob,
    errorMessage,
    sidecarMessages,
    activeJobId,
    setExcelPath,
    setPreview,
    setCurrentJob,
    setLicenseStatus,
    setModuleConfigStatus,
    setExistingJobs,
    upsertExistingJob,
    setConnectionState,
    setIsValidating,
    setIsStartingJob,
    setErrorMessage,
    pushSidecarMessage,
    setActiveJobId,
    applySidecarEvent,
  } = useJobStore();

  const [minScore, setMinScore] = useState(72);
  const [stopOnReview, setStopOnReview] = useState(true);
  const [updaterStatus, setUpdaterStatus] = useState<UpdaterStatus | null>(null);
  const [availableUpdate, setAvailableUpdate] = useState<AvailableUpdate | null>(null);
  const [isCheckingUpdate, setIsCheckingUpdate] = useState(false);
  const [isInstallingUpdate, setIsInstallingUpdate] = useState(false);
  const [licenseKey, setLicenseKey] = useState("");
  const [deviceName, setDeviceName] = useState("dmc-desktop");
  const [validatedExcelPath, setValidatedExcelPath] = useState<string | null>(null);
  const [isActivatingLicense, setIsActivatingLicense] = useState(false);
  const [browserRuntimeStatus, setBrowserRuntimeStatus] = useState<BrowserRuntimeStatus | null>(null);
  const [databaseStatus, setDatabaseStatus] = useState<DatabaseStatus | null>(null);
  const [browserRuntimeProgress, setBrowserRuntimeProgress] = useState<{
    phase: "checking" | "installing" | "verifying" | "ready" | "failed";
    message: string;
    percent: number | null;
    detail: string | null;
  } | null>(null);
  const [isBootstrappingBrowser, setIsBootstrappingBrowser] = useState(false);
  const [isCreatingBackup, setIsCreatingBackup] = useState(false);
  const [isRestoringBackup, setIsRestoringBackup] = useState(false);
  const [isExportingDiagnostics, setIsExportingDiagnostics] = useState(false);
  const [isDownloadingTemplate, setIsDownloadingTemplate] = useState(false);
  const [supportMessage, setSupportMessage] = useState<string | null>(null);
  const [updateMessage, setUpdateMessage] = useState<string | null>(null);
  const [updateProgress, setUpdateProgress] = useState<{ downloaded: number; contentLength: number | null } | null>(
    null,
  );
  const [activeModule, setActiveModule] = useState<"home" | "graduation">("home");

  const licenseBlocksStart = licenseStatus !== null && !licenseStatus.can_start_jobs;
  const browserRuntimeBlocksStart = browserRuntimeStatus !== null && !browserRuntimeStatus.installed;
  const validationBlocksStart =
    !preview || preview.rows_accepted <= 0 || validatedExcelPath !== excelPath.trim();
  const preflightRowsAccepted = validationBlocksStart ? null : preview.rows_accepted;
  const preflightRowsTotal = validationBlocksStart ? null : preview.rows_total;

  const describeLicenseStatus = useCallback((status: LicenseStatus): string => {
    if (!status.configured) {
      return messages.app.license.devMode;
    }
    if (status.last_error === "HEARTBEAT_FAILED" && status.within_offline_grace) {
      return `${messages.app.license.offlineMode} ${status.offline_grace_until ?? "-"}`;
    }
    if (!status.can_start_jobs) {
      return status.message ?? messages.app.license.reconnectRequired;
    }
    return messages.app.license.active;
  }, []);

  const handleLoadJobs = useCallback(async () => {
    try {
      const response = await listJobs();
      setExistingJobs(response.items);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }, [setErrorMessage, setExistingJobs]);

  const handleLoadUpdaterStatus = useCallback(async () => {
    try {
      setUpdaterStatus(await getUpdaterStatus());
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }, [setErrorMessage]);

  const handleLoadDatabaseStatus = useCallback(async () => {
    try {
      setDatabaseStatus(await getDatabaseStatus());
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }, [setErrorMessage]);

  const handleSyncConfig = useCallback(async () => {
    try {
      const status = await syncModuleConfig("graduation");
      setModuleConfigStatus(status);
      pushSidecarMessage(
        status.updated
          ? `config graduation อัปเดตเป็น ${status.version} แล้ว`
          : `config graduation ใช้งานเวอร์ชัน ${status.version} (${status.source})`,
      );
      if (status.last_error) {
        pushSidecarMessage(`config fallback: ${status.last_error}`);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }, [pushSidecarMessage, setErrorMessage, setModuleConfigStatus]);

  const handleRefreshLicense = useCallback(
    async (heartbeat: boolean): Promise<LicenseStatus> => {
      try {
        const status = heartbeat ? await refreshLicenseStatus() : await getLicenseStatus();
        setLicenseStatus(status);
        pushSidecarMessage(
          heartbeat
            ? `license status: ${status.status}${status.offline_mode ? " (offline)" : ""}`
            : `license local: ${status.status}`,
        );
        return status;
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : String(error));
        throw error;
      }
    },
    [pushSidecarMessage, setErrorMessage, setLicenseStatus],
  );

  const handleLoadBrowserRuntime = useCallback(async (): Promise<BrowserRuntimeStatus> => {
    try {
      const status = await getBrowserRuntimeStatus();
      setBrowserRuntimeStatus(status);
      if (status.installed) {
        setBrowserRuntimeProgress({
          phase: "ready",
          message: status.message ?? "Chromium browser runtime is ready.",
          percent: 100,
          detail: status.executable_path,
        });
      } else if (status.last_error) {
        setBrowserRuntimeProgress({
          phase: "failed",
          message: status.message ?? "Chromium browser runtime is not ready yet.",
          percent: null,
          detail: status.last_error,
        });
      } else {
        setBrowserRuntimeProgress(null);
      }
      return status;
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
      throw error;
    }
  }, [setErrorMessage]);

  const handleConnect = useCallback(async () => {
    setErrorMessage(null);
    setConnectionState("connecting");
    try {
      await initializeSidecar();
      setConnectionState("ready");
      await handleRefreshLicense(false);
      setModuleConfigStatus(await getModuleConfigStatus("graduation"));
      await handleLoadUpdaterStatus();
      await handleLoadDatabaseStatus();
      await handleLoadJobs();
      await handleLoadBrowserRuntime();
      await handleRefreshLicense(true);
      await handleSyncConfig();
    } catch (error) {
      setConnectionState("error");
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }, [
    handleLoadBrowserRuntime,
    handleLoadDatabaseStatus,
    handleLoadJobs,
    handleLoadUpdaterStatus,
    handleRefreshLicense,
    handleSyncConfig,
    setConnectionState,
    setErrorMessage,
    setModuleConfigStatus,
  ]);

  async function handleCreateBackup() {
    try {
      setIsCreatingBackup(true);
      setSupportMessage(null);
      const suggestedPath = await saveBackupDialog(`dmc-sidecar-backup-${buildTimestampSlug()}.zip`);
      if (!suggestedPath) {
        return;
      }
      const result = await createBackup(suggestedPath);
      setSupportMessage(`backup saved: ${result.backup_path}`);
      pushSidecarMessage(`backup saved: ${result.backup_path}`);
      await handleLoadDatabaseStatus();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsCreatingBackup(false);
    }
  }

  async function handleRestoreBackup() {
    try {
      setIsRestoringBackup(true);
      setSupportMessage(null);
      const archivePath = await openBackupArchiveDialog();
      if (!archivePath) {
        return;
      }
      const result = await restoreBackup(archivePath);
      setCurrentJob(null);
      setActiveJobId(null);
      setPreview(null);
      setSupportMessage(`restored from ${result.restored_from} | safety backup: ${result.safety_backup_path}`);
      pushSidecarMessage(`restore completed from ${result.restored_from}`);
      await handleLoadDatabaseStatus();
      await handleLoadJobs();
      await handleRefreshLicense(false);
      await handleLoadBrowserRuntime();
      await handleSyncConfig();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsRestoringBackup(false);
    }
  }

  async function handleExportDiagnostics() {
    try {
      setIsExportingDiagnostics(true);
      setSupportMessage(null);
      const outputPath = await saveDiagnosticsDialog(`dmc-diagnostics-${buildTimestampSlug()}.json`);
      if (!outputPath) {
        return;
      }
      const diagnostics = buildSupportDiagnostics({
        appVersion: updaterStatus?.current_version ?? "0.1.0",
        platform: typeof navigator !== "undefined" ? navigator.userAgent : "unknown",
        connectionState,
        databaseStatus,
        licenseStatus,
        moduleConfigStatus,
        browserRuntimeStatus,
        updaterStatus,
        availableUpdate,
        currentJob,
        existingJobs,
        sidecarMessageCount: sidecarMessages.length,
        hasErrorMessage: Boolean(errorMessage),
      });
      await writeTextFile(outputPath, JSON.stringify(diagnostics, null, 2));
      setSupportMessage(`diagnostics exported: ${outputPath}`);
      pushSidecarMessage(`diagnostics exported: ${outputPath}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsExportingDiagnostics(false);
    }
  }

  async function handleDownloadTemplate() {
    try {
      setIsDownloadingTemplate(true);
      setErrorMessage(null);
      setSupportMessage(null);
      const outputPath = await saveTemplateDialog("obec-study-form.xlsx");
      if (!outputPath) {
        return;
      }
      const savedPath = await copyTemplateFile(outputPath);
      setSupportMessage(`ดาวน์โหลดไฟล์ Template แล้ว: ${savedPath}`);
      pushSidecarMessage(`template saved: ${savedPath}`);
      await revealPath(savedPath);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsDownloadingTemplate(false);
    }
  }

  async function handleRevealPath(path: string) {
    try {
      setErrorMessage(null);
      await revealPath(path);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  useEffect(() => {
    if (typeof navigator === "undefined") {
      return;
    }
    setDeviceName((current) => (current !== "dmc-desktop" ? current : `desktop-${navigator.platform || "windows"}`));
  }, []);

  useEffect(() => {
    let disposed = false;
    let unlisten: (() => void) | undefined;
    let unlistenUpdater: (() => void) | undefined;

    async function bootstrap() {
      try {
        await handleConnect();
        if (disposed) {
          return;
        }
        unlisten = await listenSidecarEvents((event) => {
          if (event.type === "browser_runtime_progress") {
            setBrowserRuntimeProgress({
              phase: event.phase,
              message: event.message,
              percent: event.percent,
              detail: event.detail,
            });
          }
          applySidecarEvent(event);
        });
        unlistenUpdater = await listenUpdaterEvents((event) => {
          if (event.type === "started" || event.type === "progress") {
            setUpdateProgress({
              downloaded: event.downloaded,
              contentLength: event.contentLength,
            });
            setUpdateMessage("กำลังดาวน์โหลดอัปเดต...");
            return;
          }
          if (event.type === "finished") {
            setUpdateMessage("ดาวน์โหลดอัปเดตเสร็จแล้ว กำลังติดตั้ง...");
            return;
          }
          if (event.type === "installed") {
            setIsInstallingUpdate(false);
            setUpdateMessage("ติดตั้งอัปเดตเสร็จแล้ว กรุณาปิดแล้วเปิดแอปใหม่");
            return;
          }
          if (event.type === "error") {
            setIsInstallingUpdate(false);
            setUpdateMessage(event.message);
          }
        });
      } catch (error) {
        if (!disposed) {
          const message = error instanceof Error ? error.message : String(error);
          setConnectionState("error");
          setErrorMessage(message);
        }
      }
    }

    void bootstrap();

    return () => {
      disposed = true;
      if (unlisten) {
        void unlisten();
      }
      if (unlistenUpdater) {
        void unlistenUpdater();
      }
    };
  }, [applySidecarEvent, handleConnect, setConnectionState, setErrorMessage]);

  const handleHeartbeatRefresh = useCallback(() => handleRefreshLicense(true), [handleRefreshLicense]);

  const handleJobReconciled = useCallback(
    (status: JobStatusSnapshot) => {
      setCurrentJob(status);
      upsertExistingJob(status);
    },
    [setCurrentJob, upsertExistingJob],
  );

  const handleJobReconcileError = useCallback(
    (message: string) => {
      setErrorMessage(message);
    },
    [setErrorMessage],
  );

  usePeriodicLicenseHeartbeat({
    connectionState,
    onHeartbeat: handleHeartbeatRefresh,
  });

  useJobStatusReconciliation({
    activeJobId,
    currentJobStatus: currentJob?.status ?? null,
    onStatus: handleJobReconciled,
    onError: handleJobReconcileError,
  });

  const progressPercent = useMemo(() => {
    if (!currentJob?.total || currentJob.total <= 0) {
      return 0;
    }
    return Math.min(100, Math.max(0, Math.round((currentJob.processed / currentJob.total) * 100)));
  }, [currentJob]);

  async function handleBrowseFile() {
    try {
      const selected = await openExcelDialog();
      if (selected) {
        setExcelPath(selected);
        setPreview(null);
        setValidatedExcelPath(null);
        setErrorMessage(null);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleValidate() {
    if (!excelPath.trim()) {
      setErrorMessage("กรุณาระบุพาธไฟล์ Excel ก่อน");
      return;
    }

    setErrorMessage(null);
    setIsValidating(true);
    try {
      const response = await validateExcel(excelPath.trim());
      setPreview(response);
      setValidatedExcelPath(excelPath.trim());
      pushSidecarMessage(`validate_excel สำเร็จ: ${response.rows_accepted}/${response.rows_total}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsValidating(false);
    }
  }

  async function handleStart(dryRun: boolean) {
    const selectedExcelPath = excelPath.trim();
    if (!selectedExcelPath) {
      setErrorMessage("กรุณาระบุพาธไฟล์ Excel ก่อน");
      return;
    }

    if (validationBlocksStart) {
      setErrorMessage("กรุณาตรวจไฟล์ Excel ให้ผ่านก่อนเริ่มงาน");
      return;
    }

    if (!dryRun) {
      const rowsToWrite = preview?.rows_accepted ?? 0;
      const rowsTotal = preview?.rows_total ?? rowsToWrite;
      const confirmed =
        typeof window === "undefined" ||
        window.confirm(
          [
            "ยืนยันเริ่มงานจริง?",
            "",
            `ไฟล์: ${selectedExcelPath}`,
            `ระบบจะเขียนข้อมูล ${rowsToWrite} จาก ${rowsTotal} รายการลง DMC`,
            "",
            "ควรใช้หลังจากตรวจไฟล์หรือ Dry Run กับไฟล์นี้แล้วเท่านั้น",
          ].join("\n"),
        );
      if (!confirmed) {
        return;
      }
    }

    setErrorMessage(null);
    setIsStartingJob(true);
    try {
      const browserStatus = await handleLoadBrowserRuntime();
      if (!browserStatus.installed) {
        setErrorMessage(browserStatus.message ?? "Chromium browser runtime is not installed.");
        return;
      }
      const latestLicense = await handleRefreshLicense(true);
      if (!latestLicense.can_start_jobs) {
        setErrorMessage(latestLicense.message ?? messages.app.license.reconnectRequired);
        return;
      }
      await handleSyncConfig();
      const result = await startGraduationJob({
        jobId: buildJobId(),
        excelPath: selectedExcelPath,
        dryRun,
        stopOnReview,
        minScore,
      });
      const draft = buildDraftJob(selectedExcelPath, preview?.rows_accepted ?? null, result.job_id);
      setActiveJobId(result.job_id);
      setCurrentJob(draft);
      upsertExistingJob(draft);
      pushSidecarMessage(`${dryRun ? "เริ่ม dry run" : "เริ่มงานจริง"} แล้ว: ${result.job_id}`);
      await handleLoadJobs();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsStartingJob(false);
    }
  }

  async function handleBootstrapBrowserRuntime() {
    setErrorMessage(null);
    setIsBootstrappingBrowser(true);
    setBrowserRuntimeProgress({
      phase: "checking",
      message: "Preparing the Chromium browser runtime installer.",
      percent: 5,
      detail: null,
    });
    try {
      const status = await bootstrapBrowserRuntime();
      setBrowserRuntimeStatus(status);
      setBrowserRuntimeProgress({
        phase: status.installed ? "ready" : "failed",
        message: status.message ?? (status.installed ? "Chromium browser runtime is ready." : "Chromium browser runtime setup failed."),
        percent: status.installed ? 100 : null,
        detail: status.installed ? status.executable_path : status.last_error,
      });
      pushSidecarMessage(
        status.installed
          ? `Chromium runtime ready: ${status.install_dir}`
          : `Chromium runtime install failed: ${status.last_error ?? "unknown error"}`,
      );
      if (!status.installed) {
        setErrorMessage(status.last_error ?? status.message ?? "Chromium browser runtime is not installed.");
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsBootstrappingBrowser(false);
    }
  }

  async function handleResume() {
    if (!activeJobId) {
      return;
    }
    try {
      await resumeJob(activeJobId);
      pushSidecarMessage(`resume_job ส่งแล้ว: ${activeJobId}`);
      const status = await getJobStatus(activeJobId);
      setCurrentJob(status);
      upsertExistingJob(status);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleResumeExisting(job: JobStatusSnapshot) {
    try {
      setErrorMessage(null);
      setIsStartingJob(true);
      const response = await resumeExistingJob(job.job_id);
      if (response.accepted) {
        setActiveJobId(job.job_id);
        setCurrentJob(job);
        upsertExistingJob({ ...job, status: "running" });
        setExcelPath(job.source_file);
        pushSidecarMessage(`กลับมาทำงาน ${job.job_id} ต่อแล้ว`);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsStartingJob(false);
    }
  }

  async function handlePause() {
    if (!activeJobId) {
      return;
    }
    try {
      await pauseJob(activeJobId);
      const status = await getJobStatus(activeJobId);
      setCurrentJob(status);
      upsertExistingJob(status);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleCancel() {
    if (!activeJobId) {
      return;
    }
    if (typeof window !== "undefined" && !window.confirm("ยืนยันยกเลิกงานนี้?")) {
      return;
    }
    try {
      await cancelJob(activeJobId);
      const status = await getJobStatus(activeJobId);
      setCurrentJob(status);
      upsertExistingJob(status);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleRefreshStatus() {
    if (!activeJobId) {
      return;
    }
    try {
      const status = await getJobStatus(activeJobId);
      setCurrentJob(status);
      upsertExistingJob(status);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleActivateLicense() {
    if (!licenseKey.trim()) {
      setErrorMessage("กรุณากรอก license key ก่อน");
      return;
    }

    setErrorMessage(null);
    setIsActivatingLicense(true);
    try {
      const appVersion = updaterStatus?.current_version ?? "0.1.0";
      const status = await activateLicense({
        licenseKey: licenseKey.trim(),
        deviceName: deviceName.trim() || "dmc-desktop",
        appVersion,
      });
      setLicenseStatus(status);
      pushSidecarMessage(`activate_license สำเร็จ: ${status.status}`);
      await handleRefreshLicense(true);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsActivatingLicense(false);
    }
  }

  async function handleCheckForUpdates() {
    setUpdateMessage(null);
    setIsCheckingUpdate(true);
    try {
      const status = await getUpdaterStatus();
      setUpdaterStatus(status);
      if (!status.configured) {
        setAvailableUpdate(null);
        setUpdateMessage("ยังไม่ได้ตั้งค่า updater endpoint/public key");
        return;
      }
      const update = await checkForAppUpdate();
      setAvailableUpdate(update);
      setUpdateMessage(update ? `พบเวอร์ชันใหม่ ${update.version}` : "ยังไม่มีอัปเดตใหม่");
    } catch (error) {
      setUpdateMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsCheckingUpdate(false);
    }
  }

  async function handleInstallUpdate() {
    setUpdateMessage(null);
    setUpdateProgress(null);
    setIsInstallingUpdate(true);
    try {
      await installAppUpdate();
    } catch (error) {
      setIsInstallingUpdate(false);
      setUpdateMessage(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <main className="min-h-screen overflow-x-hidden bg-background text-foreground">
      <section className="mx-auto w-full max-w-[1440px] px-3 py-4 sm:px-5 lg:px-6">
        {activeModule === "home" ? (
          <ModuleHome
            onOpenGraduation={() => setActiveModule("graduation")}
            updaterStatus={updaterStatus}
            availableUpdate={availableUpdate}
            updateMessage={updateMessage}
            updateProgress={updateProgress}
            isCheckingUpdate={isCheckingUpdate}
            isInstallingUpdate={isInstallingUpdate}
            connectionState={connectionState}
            databaseStatus={databaseStatus}
            licenseStatus={licenseStatus}
            isCreatingBackup={isCreatingBackup}
            isRestoringBackup={isRestoringBackup}
            isExportingDiagnostics={isExportingDiagnostics}
            onCheckForUpdates={() => void handleCheckForUpdates()}
            onInstallUpdate={() => void handleInstallUpdate()}
            onRefreshDatabaseStatus={() => void handleLoadDatabaseStatus()}
            onCreateBackup={() => void handleCreateBackup()}
            onRestoreBackup={() => void handleRestoreBackup()}
            onExportDiagnostics={() => void handleExportDiagnostics()}
          />
        ) : (
          <>
            <GraduationWizard
              preview={preview}
              currentJob={currentJob}
              existingJobs={existingJobs}
              sidecarMessages={sidecarMessages}
              activeJobId={activeJobId}
              progressPercent={progressPercent}
              connectionState={connectionState}
              licenseStatus={licenseStatus}
              moduleConfigStatus={moduleConfigStatus}
              browserRuntimeStatus={browserRuntimeStatus}
              browserRuntimeProgress={browserRuntimeProgress}
              supportMessage={supportMessage}
              errorMessage={errorMessage}
              licenseKey={licenseKey}
              deviceName={deviceName}
              excelPath={excelPath}
              minScore={minScore}
              stopOnReview={stopOnReview}
              isValidating={isValidating}
              isStartingJob={isStartingJob}
              isActivatingLicense={isActivatingLicense}
              isDownloadingTemplate={isDownloadingTemplate}
              isBootstrappingBrowser={isBootstrappingBrowser}
              licenseBlocksStart={licenseBlocksStart}
              browserRuntimeBlocksStart={browserRuntimeBlocksStart}
              validationBlocksStart={validationBlocksStart}
              preflightRowsAccepted={preflightRowsAccepted}
              preflightRowsTotal={preflightRowsTotal}
              currentJobNeedsAuth={Boolean(currentJob?.needs_auth)}
              onBackHome={() => setActiveModule("home")}
              onLicenseKeyChange={setLicenseKey}
              onDeviceNameChange={setDeviceName}
              onExcelPathChange={(value) => {
                setExcelPath(value);
                setPreview(null);
                setValidatedExcelPath(null);
              }}
              onMinScoreChange={setMinScore}
              onStopOnReviewChange={setStopOnReview}
              onConnect={() => void handleConnect()}
              onRefreshJobs={() => void handleLoadJobs()}
              onRefreshLicense={() => void handleRefreshLicense(true)}
              onSyncConfig={() => void handleSyncConfig()}
              onValidate={() => void handleValidate()}
              onStartDryRun={() => void handleStart(true)}
              onStartLive={() => void handleStart(false)}
              onRefreshStatus={() => void handleRefreshStatus()}
              onPause={() => void handlePause()}
              onResume={() => void handleResume()}
              onCancel={() => void handleCancel()}
              onActivateLicense={() => void handleActivateLicense()}
              onBrowseFile={() => void handleBrowseFile()}
              onDownloadTemplate={() => void handleDownloadTemplate()}
              onBootstrapBrowserRuntime={() => void handleBootstrapBrowserRuntime()}
              onReloadBrowserRuntime={() => void handleLoadBrowserRuntime()}
              onSelectJob={(job) => {
                setActiveJobId(job.job_id);
                setCurrentJob(job);
                setExcelPath(job.source_file);
              }}
              onResumeExisting={(job) => void handleResumeExisting(job)}
              onRevealPath={(path) => void handleRevealPath(path)}
              describeLicenseStatus={describeLicenseStatus}
            />
          </>
        )}
      </section>
    </main>
  );
}
