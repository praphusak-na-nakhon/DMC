import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import messages from "./i18n/th.json";
import {
  archiveOldJobs,
  bootstrapBrowserRuntime,
  checkForAppUpdate,
  copyTemplateFile,
  createBackup,
  getAccountStatus,
  getBrowserRuntimeStatus,
  getDatabaseStatus,
  getJobStatus,
  getModuleCatalog,
  getModuleConfigStatus,
  getUpdaterStatus,
  initializeSidecar,
  installAppUpdate,
  listJobs,
  listenSidecarEvents,
  listenUpdaterEvents,
  openBackupArchiveDialog,
  openExcelDialog,
  refreshWallet,
  restoreBackup,
  revealPath,
  saveBackupDialog,
  saveDiagnosticsDialog,
  saveTemplateDialog,
  signIn,
  signOut,
  startCurrentStudentsImportJob,
  startGraduationJob,
  syncModuleConfig,
  validateExcel,
  writeTextFile,
  pauseJob,
  resumeExistingJob,
  resumeJob,
  cancelJob,
} from "./lib/rpcClient";
import { buildDraftJob, buildJobId, buildSupportDiagnostics, buildTimestampSlug, isActiveJobStatus } from "./lib/appUi";
import { describeUserFacingError } from "./lib/errorMessages";
import { useJobStatusReconciliation } from "./hooks/useJobStatusReconciliation";
import { useJobStore } from "./stores/useJobStore";
import { GraduationWizard } from "./components/GraduationWizard";
import { FormConverterPage } from "./components/FormConverterPage";
import { CurrentStudentsPage } from "./components/CurrentStudentsPage";
import { ModuleHome } from "./components/ModuleHome";
import { PsarReadinessPage } from "./components/PsarReadinessPage";
import { StudentBasicInfoPage } from "./components/StudentBasicInfoPage";
import { AccountSignInPage } from "./components/AccountSignInPage";
import { CreditTopupPage } from "./components/CreditTopupPage";
import { AlertDialog } from "./components/ui/alert-dialog";
import type { ModuleId } from "./lib/moduleCatalog";
import type {
  AvailableUpdate,
  BrowserRuntimeStatus,
  DatabaseStatus,
  JobStatusSnapshot,
  UpdaterStatus,
} from "./types/contracts";

function toUserError(error: unknown): string {
  return describeUserFacingError(error);
}

function errorHasCode(error: unknown, code: string): boolean {
  const raw = error instanceof Error ? error.message : String(error);
  return raw.includes(code);
}

type ConfirmDialogState = {
  type: "archive_old_jobs" | "start_live" | "start_current_students_live" | "cancel_job" | "close_active_job";
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  variant?: "default" | "destructive";
};

async function requestWindowAttention(): Promise<void> {
  try {
    const { getCurrentWindow, UserAttentionType } = await import("@tauri-apps/api/window");
    await getCurrentWindow().requestUserAttention(UserAttentionType.Informational);
  } catch {
    // Browser preview and test runs do not expose a Tauri window.
  }
}

async function notifyLongRunningJob(title: string, body: string): Promise<void> {
  if (typeof window !== "undefined" && "Notification" in window) {
    try {
      if (Notification.permission === "granted") {
        new Notification(title, { body });
      } else if (Notification.permission === "default") {
        const permission = await Notification.requestPermission();
        if (permission === "granted") {
          new Notification(title, { body });
        }
      }
    } catch {
      // Some WebView environments expose Notification but block it at runtime.
    }
  }
  await requestWindowAttention();
}

async function destroyCurrentWindow(): Promise<void> {
  const { getCurrentWindow } = await import("@tauri-apps/api/window");
  await getCurrentWindow().destroy();
}

export function App() {
  const {
    preview,
    currentJob,
    accountStatus,
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
    setAccountStatus,
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
  const [accountEmail, setAccountEmail] = useState("");
  const [accountPassword, setAccountPassword] = useState("");
  const [deviceName, setDeviceName] = useState("dmc-desktop");
  const [validatedExcelPath, setValidatedExcelPath] = useState<string | null>(null);
  const [isSigningIn, setIsSigningIn] = useState(false);
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
  const [isArchivingJobs, setIsArchivingJobs] = useState(false);
  const [supportMessage, setSupportMessage] = useState<string | null>(null);
  const [updateMessage, setUpdateMessage] = useState<string | null>(null);
  const [updateProgress, setUpdateProgress] = useState<{ downloaded: number; contentLength: number | null } | null>(
    null,
  );
  const [activeModule, setActiveModule] = useState<"home" | "signIn" | "credits" | ModuleId>("home");
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState | null>(null);
  const mountedRef = useRef(false);
  const activeJobRef = useRef(false);
  const pendingCurrentStudentsStartRef = useRef<{ jsonPath: string; rowsToWrite: number } | null>(null);
  const notifiedDoneJobRef = useRef<string | null>(null);
  const notifiedFailedJobRef = useRef<string | null>(null);
  const notifiedNeedsAuthJobRef = useRef<string | null>(null);

  const validationBlocksStart =
    !preview || preview.rows_accepted <= 0 || validatedExcelPath !== excelPath.trim();
  const preflightRowsAccepted = validationBlocksStart ? null : preview.rows_accepted;
  const preflightRowsTotal = validationBlocksStart ? null : preview.rows_total;
  const estimatedCredits = preflightRowsAccepted ?? preview?.rows_accepted ?? 0;
  const browserRuntimeBlocksStart = browserRuntimeStatus !== null && !browserRuntimeStatus.installed;
  const accountBlocksStart =
    !accountStatus?.signed_in ||
    !accountStatus.can_start_credit_jobs ||
    (estimatedCredits > 0 && (accountStatus.wallet?.available ?? 0) < estimatedCredits);
  const hasActiveJob = Boolean(currentJob && isActiveJobStatus(currentJob.status));

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
      pushSidecarMessage(`config graduation ${status.version} (${status.source})`);
      if (status.last_error) {
        pushSidecarMessage(`config fallback: ${status.last_error}`);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }, [pushSidecarMessage, setErrorMessage, setModuleConfigStatus]);

  const handleRefreshAccount = useCallback(
    async (forceWallet: boolean): Promise<void> => {
      try {
        const status = forceWallet ? await refreshWallet() : await getAccountStatus();
        setAccountStatus(status);
        pushSidecarMessage(
          status.signed_in
            ? `account: ${status.email ?? status.user_id ?? "signed in"} | available credits ${status.wallet?.available ?? "-"}`
            : "account: signed out",
        );
      } catch (error) {
        setErrorMessage(toUserError(error));
        throw error;
      }
    },
    [pushSidecarMessage, setAccountStatus, setErrorMessage],
  );

  const handleLoadModuleCatalog = useCallback(async () => {
    try {
      const catalog = await getModuleCatalog();
      pushSidecarMessage(`module catalog loaded: ${catalog.modules.length} modules`);
    } catch (error) {
      setErrorMessage(toUserError(error));
    }
  }, [pushSidecarMessage, setErrorMessage]);

  const handleLoadBrowserRuntime = useCallback(async (): Promise<BrowserRuntimeStatus> => {
    try {
      const status = await getBrowserRuntimeStatus();
      setBrowserRuntimeStatus(status);
      if (status.installed) {
        setBrowserRuntimeProgress({
          phase: "ready",
          message: status.message ?? "Chromium พร้อมใช้งาน",
          percent: 100,
          detail: status.executable_path,
        });
      } else if (status.last_error) {
        setBrowserRuntimeProgress({
          phase: "failed",
          message: status.message ?? "Chromium ยังไม่พร้อมใช้งาน",
          percent: null,
          detail: status.last_error,
        });
      } else {
        setBrowserRuntimeProgress(null);
      }
      return status;
    } catch (error) {
      setErrorMessage(toUserError(error));
      throw error;
    }
  }, [setErrorMessage]);

  const handleConnect = useCallback(async (isActive: () => boolean = () => mountedRef.current) => {
    if (!isActive()) {
      return;
    }
    setErrorMessage(null);
    setConnectionState("connecting");
    try {
      await initializeSidecar();
      if (!isActive()) {
        return;
      }
      setConnectionState("ready");
      await handleRefreshAccount(false);
      if (!isActive()) {
        return;
      }
      const configStatus = await getModuleConfigStatus("graduation");
      if (!isActive()) {
        return;
      }
      setModuleConfigStatus(configStatus);
      await handleLoadUpdaterStatus();
      if (!isActive()) {
        return;
      }
      await handleLoadDatabaseStatus();
      if (!isActive()) {
        return;
      }
      await handleLoadJobs();
      if (!isActive()) {
        return;
      }
      await handleLoadBrowserRuntime();
      if (!isActive()) {
        return;
      }
      await handleLoadModuleCatalog();
      if (!isActive()) {
        return;
      }
      await handleSyncConfig();
    } catch (error) {
      if (!isActive()) {
        return;
      }
      setConnectionState("error");
      setErrorMessage(toUserError(error));
    }
  }, [
    handleLoadBrowserRuntime,
    handleLoadDatabaseStatus,
    handleLoadJobs,
    handleLoadModuleCatalog,
    handleLoadUpdaterStatus,
    handleRefreshAccount,
    handleSyncConfig,
    setConnectionState,
    setErrorMessage,
    setModuleConfigStatus,
  ]);

  async function handleSignIn() {
    if (!accountEmail.trim() || !accountPassword) {
      setErrorMessage(messages.app.account.missingCredentials);
      return;
    }
    try {
      setIsSigningIn(true);
      setErrorMessage(null);
      const status = await signIn({
        email: accountEmail.trim(),
        password: accountPassword,
        deviceName: deviceName.trim() || "dmc-desktop",
        appVersion: updaterStatus?.current_version ?? "0.1.0",
      });
      setAccountStatus(status);
      setAccountPassword("");
      pushSidecarMessage(`signed in: ${status.email ?? status.user_id ?? "-"}`);
      await handleLoadModuleCatalog();
      setActiveModule("home");
    } catch (error) {
      setErrorMessage(toUserError(error));
    } finally {
      setIsSigningIn(false);
    }
  }

  async function handleSignOut() {
    try {
      setErrorMessage(null);
      const status = await signOut();
      setAccountStatus(status);
      pushSidecarMessage("signed out");
    } catch (error) {
      setErrorMessage(toUserError(error));
    }
  }

  async function handleCreateBackup() {
    try {
      setIsCreatingBackup(true);
      setSupportMessage(null);
      const suggestedPath = await saveBackupDialog(`dmc-sidecar-backup-${buildTimestampSlug()}.zip`);
      if (!suggestedPath) {
        return;
      }
      const result = await createBackup(suggestedPath);
      setSupportMessage(`สำรองข้อมูลแล้ว: ${result.backup_path}`);
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
      setSupportMessage(`กู้คืนจาก ${result.restored_from} | safety backup: ${result.safety_backup_path}`);
      pushSidecarMessage(`restore completed from ${result.restored_from}`);
      await handleLoadDatabaseStatus();
      await handleLoadJobs();
      await handleRefreshAccount(false);
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
        accountStatus,
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
      setSupportMessage(`สร้างไฟล์วินิจฉัยแล้ว: ${outputPath}`);
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
      setSupportMessage(`ดาวน์โหลดไฟล์ต้นแบบแล้ว: ${savedPath}`);
      pushSidecarMessage(`template saved: ${savedPath}`);
      await revealPath(savedPath);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsDownloadingTemplate(false);
    }
  }

  async function handleArchiveOldJobs(confirmed = false) {
    if (!confirmed) {
      setConfirmDialog({
        type: "archive_old_jobs",
        title: "ล้างประวัติงานเก่า",
        description: "ระบบจะล้างงานเก่าที่จบแล้ว โดยเก็บ 20 รายการล่าสุดไว้ใน local checkpoint",
        confirmLabel: "ล้างประวัติ",
        cancelLabel: "ยกเลิก",
        variant: "destructive",
      });
      return;
    }
    try {
      setIsArchivingJobs(true);
      setErrorMessage(null);
      setSupportMessage(null);
      const result = await archiveOldJobs(20);
      setSupportMessage(`ล้างประวัติงานเก่าแล้ว ${result.archived} รายการ และเก็บล่าสุดไว้ ${result.kept} รายการ`);
      await handleLoadJobs();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsArchivingJobs(false);
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
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    activeJobRef.current = hasActiveJob;
  }, [hasActiveJob]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    function warnBeforeUnload(event: BeforeUnloadEvent) {
      if (!activeJobRef.current) {
        return;
      }
      event.preventDefault();
      event.returnValue = "";
    }

    let disposed = false;
    let unlistenClose: (() => void) | undefined;

    async function bindCloseGuard() {
      try {
        const { getCurrentWindow } = await import("@tauri-apps/api/window");
        if (disposed) {
          return;
        }
        unlistenClose = await getCurrentWindow().onCloseRequested((event) => {
          if (!activeJobRef.current) {
            return;
          }
          event.preventDefault();
          setConfirmDialog({
            type: "close_active_job",
            title: "ยังมีงานที่กำลังทำอยู่",
            description:
              "งาน automation ยังไม่จบ ถ้าปิดหน้าต่างตอนนี้งานจะหยุดและอาจต้องกลับมาทำต่อจาก checkpoint ภายหลัง",
            confirmLabel: "ปิดหน้าต่าง",
            cancelLabel: "ทำงานต่อ",
            variant: "destructive",
          });
        });
      } catch {
        // Browser preview and tests do not have a Tauri window.
      }
    }

    window.addEventListener("beforeunload", warnBeforeUnload);
    void bindCloseGuard();

    return () => {
      disposed = true;
      window.removeEventListener("beforeunload", warnBeforeUnload);
      if (unlistenClose) {
        void unlistenClose();
      }
    };
  }, []);

  useEffect(() => {
    if (!currentJob) {
      return;
    }
    if (currentJob.needs_auth && notifiedNeedsAuthJobRef.current !== currentJob.job_id) {
      notifiedNeedsAuthJobRef.current = currentJob.job_id;
      void notifyLongRunningJob(
        "DMC Assistant รอการยืนยันตัวตน",
        "กรุณา login ใน Chromium ที่เปิดอยู่ แล้วกลับมากดทำต่อหลังยืนยันตัวตน",
      );
    }
    if (currentJob.status === "done" && notifiedDoneJobRef.current !== currentJob.job_id) {
      notifiedDoneJobRef.current = currentJob.job_id;
      void notifyLongRunningJob("DMC Assistant ทำงานเสร็จแล้ว", "งานกรอกข้อมูล DMC เสร็จสิ้นแล้ว");
    }
    if (currentJob.status === "failed" && notifiedFailedJobRef.current !== currentJob.job_id) {
      notifiedFailedJobRef.current = currentJob.job_id;
      void notifyLongRunningJob("DMC Assistant ทำงานไม่สำเร็จ", "กรุณากลับมาตรวจรายละเอียดในแอป");
    }
  }, [currentJob]);

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
        await handleConnect(() => !disposed);
        if (disposed) {
          return;
        }
        unlisten = await listenSidecarEvents((event) => {
          if (disposed) {
            return;
          }
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
          if (disposed) {
            return;
          }
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
          const message = toUserError(error);
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

  const handleJobReconciled = useCallback(
    (status: JobStatusSnapshot) => {
      setCurrentJob(status);
      upsertExistingJob(status);
      if (status.credit_status === "finalized") {
        void handleRefreshAccount(true);
      }
    },
    [handleRefreshAccount, setCurrentJob, upsertExistingJob],
  );

  const handleJobReconcileError = useCallback(
    (message: string) => {
      setErrorMessage(message);
    },
    [setErrorMessage],
  );

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
      setErrorMessage("กรุณาระบุไฟล์ Excel ก่อน");
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

  async function handleStart(dryRun: boolean, confirmed = false) {
    const selectedExcelPath = excelPath.trim();
    if (!selectedExcelPath) {
      setErrorMessage("กรุณาระบุไฟล์ Excel ก่อน");
      return;
    }
    if (validationBlocksStart) {
      setErrorMessage("กรุณาตรวจไฟล์ Excel ให้ผ่านก่อนเริ่มงาน");
      return;
    }

    const rowsToWrite = preview?.rows_accepted ?? 0;
    if (!dryRun) {
      if (!accountStatus?.signed_in) {
        setErrorMessage(messages.app.account.signInBeforeLive);
        return;
      }
      if ((accountStatus.wallet?.available ?? 0) < rowsToWrite) {
        setErrorMessage(messages.app.account.insufficientCredits);
        return;
      }
      const rowsTotal = preview?.rows_total ?? rowsToWrite;
      if (!confirmed) {
        setConfirmDialog({
          type: "start_live",
          title: "ยืนยันเริ่มส่งข้อมูลเข้า DMC",
          description: [
            `ไฟล์: ${selectedExcelPath}`,
            `ระบบจะส่งข้อมูล ${rowsToWrite} จาก ${rowsTotal} รายการเข้า DMC`,
            `เครดิตที่จะกันไว้: ${rowsToWrite}`,
            "",
            messages.app.account.reserveNotice,
          ].join("\n"),
          confirmLabel: "เริ่มงานจริง",
          cancelLabel: "ตรวจอีกครั้ง",
          variant: "destructive",
        });
        return;
      }
    }

    setErrorMessage(null);
    setIsStartingJob(true);
    try {
      const browserStatus = await handleLoadBrowserRuntime();
      if (!browserStatus.installed) {
        setErrorMessage(browserStatus.message ?? "ยังไม่ได้ติดตั้ง Chromium runtime");
        return;
      }
      if (!dryRun) {
        await handleRefreshAccount(true);
        const latestAccount = await getAccountStatus();
        setAccountStatus(latestAccount);
        if (!latestAccount.signed_in || !latestAccount.can_start_credit_jobs) {
          setErrorMessage(latestAccount.message ?? messages.app.account.signInBeforeLive);
          return;
        }
        if ((latestAccount.wallet?.available ?? 0) < rowsToWrite) {
          setErrorMessage(messages.app.account.insufficientCredits);
          return;
        }
      }
      await handleSyncConfig();
      const result = await startGraduationJob({
        jobId: buildJobId(),
        excelPath: selectedExcelPath,
        dryRun,
        stopOnReview,
        minScore,
        estimatedCredits: rowsToWrite,
      });
      const draft = buildDraftJob(selectedExcelPath, rowsToWrite, result.job_id);
      draft.credit_reservation_id = result.credit_reservation_id;
      draft.credits_reserved = result.credits_reserved;
      draft.credit_status = result.credit_reservation_id ? "reserved" : dryRun ? null : "reserving";
      setActiveJobId(result.job_id);
      setCurrentJob(draft);
      upsertExistingJob(draft);
      pushSidecarMessage(`${dryRun ? "เริ่ม dry run" : "เริ่มงานจริง"} แล้ว: ${result.job_id}`);
      if (!dryRun) {
        await handleRefreshAccount(true);
      }
      await handleLoadJobs();
    } catch (error) {
      setErrorMessage(toUserError(error));
    } finally {
      setIsStartingJob(false);
    }
  }

  async function handleStartCurrentStudentsImport(
    jsonPath: string,
    rowsToWrite: number,
    dryRun: boolean,
    confirmed = false,
  ) {
    const selectedJsonPath = jsonPath.trim();
    if (!selectedJsonPath) {
      setErrorMessage("กรุณาเลือกไฟล์ JSON ก่อนเริ่มงาน");
      return;
    }
    if (!/\.json$/i.test(selectedJsonPath)) {
      setErrorMessage("งานย้ายเข้านักเรียนผ่านหน้า DMC รองรับเฉพาะไฟล์ JSON");
      return;
    }
    if (rowsToWrite <= 0) {
      setErrorMessage("ไม่มีรายการพร้อมส่งเข้า DMC");
      return;
    }
    if (currentJob && isActiveJobStatus(currentJob.status)) {
      setErrorMessage("กรุณาหยุดหรืองานเดิมให้จบก่อนเริ่มงานใหม่");
      return;
    }
    if (!dryRun) {
      if (!accountStatus?.signed_in) {
        setErrorMessage(messages.app.account.signInBeforeLive);
        return;
      }
      if ((accountStatus.wallet?.available ?? 0) < rowsToWrite) {
        setErrorMessage(messages.app.account.insufficientCredits);
        return;
      }
      if (!confirmed) {
        pendingCurrentStudentsStartRef.current = { jsonPath: selectedJsonPath, rowsToWrite };
        setConfirmDialog({
          type: "start_current_students_live",
          title: "ยืนยันส่งย้ายเข้านักเรียนเข้า DMC",
          description: [
            `ไฟล์: ${selectedJsonPath}`,
            `ระบบจะกรอกและบันทึกหน้า DMC จำนวน ${rowsToWrite} รายการ`,
            `เครดิตที่จะกันไว้: ${rowsToWrite}`,
            "",
            messages.app.account.reserveNotice,
          ].join("\n"),
          confirmLabel: "เริ่มงานจริง",
          cancelLabel: "ตรวจอีกครั้ง",
          variant: "destructive",
        });
        return;
      }
    }

    setErrorMessage(null);
    setIsStartingJob(true);
    try {
      const browserStatus = await handleLoadBrowserRuntime();
      if (!browserStatus.installed) {
        setErrorMessage(browserStatus.message ?? "ยังไม่ได้ติดตั้ง Chromium runtime");
        return;
      }
      if (!dryRun) {
        let latestAccount = accountStatus;
        let usingCachedAccountAfterCloudFailure = false;
        try {
          await handleRefreshAccount(true);
          latestAccount = await getAccountStatus();
          setAccountStatus(latestAccount);
        } catch (error) {
          if (!errorHasCode(error, "ACCOUNT_CLOUD_UNAVAILABLE") || !accountStatus?.signed_in) {
            throw error;
          }
          usingCachedAccountAfterCloudFailure = true;
          latestAccount = accountStatus;
          pushSidecarMessage(
            "account cloud unavailable; using cached credit snapshot for currentStudents and letting sidecar bypass reservation",
          );
        }
        if (!latestAccount?.signed_in || (!latestAccount.can_start_credit_jobs && !usingCachedAccountAfterCloudFailure)) {
          setErrorMessage(latestAccount.message ?? messages.app.account.signInBeforeLive);
          return;
        }
        if ((latestAccount.wallet?.available ?? 0) < rowsToWrite) {
          setErrorMessage(messages.app.account.insufficientCredits);
          return;
        }
      }
      const result = await startCurrentStudentsImportJob({
        jobId: buildJobId(),
        jsonPath: selectedJsonPath,
        dryRun,
        estimatedCredits: rowsToWrite,
      });
      const draft = buildDraftJob(selectedJsonPath, rowsToWrite, result.job_id);
      draft.module = "currentStudents";
      draft.credit_reservation_id = result.credit_reservation_id;
      draft.credits_reserved = result.credits_reserved;
      draft.credit_status = result.credit_reservation_id ? "reserved" : dryRun ? null : "reserving";
      setActiveJobId(result.job_id);
      setCurrentJob(draft);
      upsertExistingJob(draft);
      pushSidecarMessage(`${dryRun ? "เริ่ม dry run ย้ายเข้า" : "เริ่มงานย้ายเข้า DMC จริง"}: ${result.job_id}`);
      if (!dryRun) {
        try {
          await handleRefreshAccount(true);
        } catch (error) {
          if (!errorHasCode(error, "ACCOUNT_CLOUD_UNAVAILABLE")) {
            throw error;
          }
          pushSidecarMessage("account cloud unavailable after starting currentStudents; job is running with local bypass");
        }
      }
      await handleLoadJobs();
    } catch (error) {
      setErrorMessage(toUserError(error));
    } finally {
      setIsStartingJob(false);
    }
  }

  async function handleBootstrapBrowserRuntime() {
    setErrorMessage(null);
    setIsBootstrappingBrowser(true);
    setBrowserRuntimeProgress({
      phase: "checking",
      message: "กำลังเตรียมตัวติดตั้ง Chromium runtime",
      percent: 5,
      detail: null,
    });
    try {
      const status = await bootstrapBrowserRuntime();
      setBrowserRuntimeStatus(status);
      setBrowserRuntimeProgress({
        phase: status.installed ? "ready" : "failed",
        message: status.message ?? (status.installed ? "Chromium พร้อมใช้งาน" : "ติดตั้ง Chromium runtime ไม่สำเร็จ"),
        percent: status.installed ? 100 : null,
        detail: status.installed ? status.executable_path : status.last_error,
      });
      pushSidecarMessage(
        status.installed
          ? `Chromium runtime พร้อมใช้งาน: ${status.install_dir}`
          : `ติดตั้ง Chromium runtime ไม่สำเร็จ: ${status.last_error ?? "unknown error"}`,
      );
      if (!status.installed) {
        setErrorMessage(status.last_error ?? status.message ?? "ยังไม่ได้ติดตั้ง Chromium runtime");
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

  async function handleCancel(confirmed = false) {
    if (!activeJobId) {
      return;
    }
    if (!confirmed) {
      setConfirmDialog({
        type: "cancel_job",
        title: "ยกเลิกงานนี้",
        description: "งานที่กำลังทำอยู่จะหยุดที่ checkpoint ล่าสุด และระบบจะสรุปเครดิตตามรายการที่ทำไปแล้ว",
        confirmLabel: "ยกเลิกงาน",
        cancelLabel: "ทำงานต่อ",
        variant: "destructive",
      });
      return;
    }
    try {
      await cancelJob(activeJobId);
      const status = await getJobStatus(activeJobId);
      setCurrentJob(status);
      upsertExistingJob(status);
      if (status.credit_status === "finalized") {
        await handleRefreshAccount(true);
      }
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
      if (status.credit_status === "finalized") {
        await handleRefreshAccount(true);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
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

  function handleConfirmDialog() {
    const dialog = confirmDialog;
    if (!dialog) {
      return;
    }
    setConfirmDialog(null);
    if (dialog.type === "archive_old_jobs") {
      void handleArchiveOldJobs(true);
      return;
    }
    if (dialog.type === "start_live") {
      void handleStart(false, true);
      return;
    }
    if (dialog.type === "start_current_students_live") {
      const pending = pendingCurrentStudentsStartRef.current;
      pendingCurrentStudentsStartRef.current = null;
      if (pending) {
        void handleStartCurrentStudentsImport(pending.jsonPath, pending.rowsToWrite, false, true);
      }
      return;
    }
    if (dialog.type === "cancel_job") {
      void handleCancel(true);
      return;
    }
    if (dialog.type === "close_active_job") {
      void destroyCurrentWindow().catch((error) => {
        setErrorMessage(error instanceof Error ? error.message : String(error));
      });
    }
  }

  return (
    <>
    {confirmDialog ? (
      <AlertDialog
        open
        title={confirmDialog.title}
        description={confirmDialog.description}
        confirmLabel={confirmDialog.confirmLabel}
        cancelLabel={confirmDialog.cancelLabel}
        variant={confirmDialog.variant}
        onCancel={() => setConfirmDialog(null)}
        onConfirm={handleConfirmDialog}
      />
    ) : null}
    <main className="min-h-screen overflow-x-hidden bg-[#f7faff] text-foreground">
      <section className="mx-auto w-full max-w-[1600px] px-5 py-6 sm:px-8 lg:px-12">
        {activeModule === "home" ? (
          <ModuleHome
            onOpenModule={(moduleId) => setActiveModule(moduleId)}
            connectionState={connectionState}
            accountStatus={accountStatus}
            errorMessage={errorMessage}
            onOpenSignIn={() => setActiveModule("signIn")}
            onOpenTopup={() => setActiveModule("credits")}
            onSignOut={() => void handleSignOut()}
            onRetryRuntime={() => void handleConnect()}
          />
        ) : activeModule === "credits" ? (
          <CreditTopupPage
            accountStatus={accountStatus}
            onBackHome={() => setActiveModule("home")}
            onOpenSignIn={() => setActiveModule("signIn")}
          />
        ) : activeModule === "signIn" ? (
          <AccountSignInPage
            accountStatus={accountStatus}
            accountEmail={accountEmail}
            accountPassword={accountPassword}
            errorMessage={errorMessage}
            isSigningIn={isSigningIn}
            onBackHome={() => setActiveModule("home")}
            onAccountEmailChange={setAccountEmail}
            onAccountPasswordChange={setAccountPassword}
            onSignIn={() => void handleSignIn()}
            onSignOut={() => void handleSignOut()}
            onRefreshWallet={() => void handleRefreshAccount(true)}
          />
        ) : activeModule === "formConverter" ? (
          <FormConverterPage
            onBackHome={() => setActiveModule("home")}
            onRevealPath={(path) => void handleRevealPath(path)}
            onRetryRuntime={() => void handleConnect()}
          />
        ) : activeModule === "studentBasicInfo" ? (
          <StudentBasicInfoPage
            onBackHome={() => setActiveModule("home")}
            onRevealPath={(path) => void handleRevealPath(path)}
            onRetryRuntime={() => void handleConnect()}
          />
        ) : activeModule === "psar" ? (
          <PsarReadinessPage
            onBackHome={() => setActiveModule("home")}
            onRevealPath={(path) => void handleRevealPath(path)}
          />
        ) : activeModule === "currentStudents" ? (
          <CurrentStudentsPage
            onBackHome={() => setActiveModule("home")}
            onRevealPath={(path) => void handleRevealPath(path)}
            onRetryRuntime={() => void handleConnect()}
            currentJob={currentJob?.module === "currentStudents" ? currentJob : null}
            activeJobId={currentJob?.module === "currentStudents" ? activeJobId : null}
            progressPercent={currentJob?.module === "currentStudents" ? progressPercent : 0}
            isStartingJob={isStartingJob}
            externalErrorMessage={errorMessage}
            onStartDmcImport={(jsonPath, readyRows, dryRun) =>
              handleStartCurrentStudentsImport(jsonPath, readyRows, dryRun)
            }
            onRefreshStatus={() => void handleRefreshStatus()}
            onPause={() => void handlePause()}
            onResume={() => void handleResume()}
            onCancel={() => void handleCancel()}
          />
        ) : (
          <GraduationWizard
            preview={preview}
            currentJob={currentJob}
            existingJobs={existingJobs}
            sidecarMessages={sidecarMessages}
            activeJobId={activeJobId}
            progressPercent={progressPercent}
            connectionState={connectionState}
            accountStatus={accountStatus}
            moduleConfigStatus={moduleConfigStatus}
            browserRuntimeStatus={browserRuntimeStatus}
            browserRuntimeProgress={browserRuntimeProgress}
            supportMessage={supportMessage}
            errorMessage={errorMessage}
            excelPath={excelPath}
            minScore={minScore}
            stopOnReview={stopOnReview}
            isValidating={isValidating}
            isStartingJob={isStartingJob}
            isDownloadingTemplate={isDownloadingTemplate}
            isArchivingJobs={isArchivingJobs}
            isBootstrappingBrowser={isBootstrappingBrowser}
            accountBlocksStart={accountBlocksStart}
            browserRuntimeBlocksStart={browserRuntimeBlocksStart}
            validationBlocksStart={validationBlocksStart}
            preflightRowsAccepted={preflightRowsAccepted}
            preflightRowsTotal={preflightRowsTotal}
            currentJobNeedsAuth={Boolean(currentJob?.needs_auth)}
            onBackHome={() => setActiveModule("home")}
            onExcelPathChange={(value) => {
              setExcelPath(value);
              setPreview(null);
              setValidatedExcelPath(null);
            }}
            onMinScoreChange={setMinScore}
            onStopOnReviewChange={setStopOnReview}
            onConnect={() => void handleConnect()}
            onRefreshJobs={() => void handleLoadJobs()}
            onRefreshWallet={() => void handleRefreshAccount(true)}
            onSyncConfig={() => void handleSyncConfig()}
            onValidate={() => void handleValidate()}
            onStartDryRun={() => void handleStart(true)}
            onStartLive={() => void handleStart(false)}
            onRefreshStatus={() => void handleRefreshStatus()}
            onPause={() => void handlePause()}
            onResume={() => void handleResume()}
            onCancel={() => void handleCancel()}
            onBrowseFile={() => void handleBrowseFile()}
            onDownloadTemplate={() => void handleDownloadTemplate()}
            onArchiveOldJobs={() => void handleArchiveOldJobs()}
            onBootstrapBrowserRuntime={() => void handleBootstrapBrowserRuntime()}
            onReloadBrowserRuntime={() => void handleLoadBrowserRuntime()}
            onSelectJob={(job) => {
              setActiveJobId(job.job_id);
              setCurrentJob(job);
              setExcelPath(job.source_file);
            }}
            onResumeExisting={(job) => void handleResumeExisting(job)}
            onRevealPath={(path) => void handleRevealPath(path)}
          />
        )}
      </section>
    </main>
    </>
  );
}
