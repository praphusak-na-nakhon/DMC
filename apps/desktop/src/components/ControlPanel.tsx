import type { CSSProperties } from "react";
import messages from "../i18n/th.json";
import {
  buttonStyle,
  cardStyle,
  describeBrowserRuntimePhase,
  formatBytes,
  formatTimestamp,
} from "../lib/appUi";
import type {
  AvailableUpdate,
  BrowserRuntimeStatus,
  LicenseStatus,
  ModuleConfigStatus,
  UpdaterStatus,
} from "../types/contracts";

type BrowserRuntimeProgress = {
  phase: "checking" | "installing" | "verifying" | "ready" | "failed";
  message: string;
  percent: number | null;
  detail: string | null;
} | null;

type ConnectionState = "idle" | "connecting" | "ready" | "error";

type ControlPanelProps = {
  connectionState: ConnectionState;
  licenseStatus: LicenseStatus | null;
  moduleConfigStatus: ModuleConfigStatus | null;
  browserRuntimeStatus: BrowserRuntimeStatus | null;
  browserRuntimeProgress: BrowserRuntimeProgress;
  updaterStatus: UpdaterStatus | null;
  availableUpdate: AvailableUpdate | null;
  updateMessage: string | null;
  updateProgress: { downloaded: number; contentLength: number | null } | null;
  supportMessage: string | null;
  errorMessage: string | null;
  licenseKey: string;
  deviceName: string;
  excelPath: string;
  minScore: number;
  stopOnReview: boolean;
  isValidating: boolean;
  isStartingJob: boolean;
  isActivatingLicense: boolean;
  isBootstrappingBrowser: boolean;
  isCheckingUpdate: boolean;
  isInstallingUpdate: boolean;
  licenseBlocksStart: boolean;
  browserRuntimeBlocksStart: boolean;
  validationBlocksStart: boolean;
  onLicenseKeyChange: (value: string) => void;
  onDeviceNameChange: (value: string) => void;
  onExcelPathChange: (value: string) => void;
  onMinScoreChange: (value: number) => void;
  onStopOnReviewChange: (value: boolean) => void;
  onConnect: () => void;
  onRefreshJobs: () => void;
  onRefreshLicense: () => void;
  onSyncConfig: () => void;
  onValidate: () => void;
  onStartDryRun: () => void;
  onStartLive: () => void;
  onRefreshStatus: () => void;
  onPause: () => void;
  onResume: () => void;
  onCancel: () => void;
  onActivateLicense: () => void;
  onBrowseFile: () => void;
  onBootstrapBrowserRuntime: () => void;
  onReloadBrowserRuntime: () => void;
  onCheckForUpdates: () => void;
  onInstallUpdate: () => void;
  describeLicenseStatus: (status: LicenseStatus) => string;
  activeJobId: string | null;
  currentJobNeedsAuth: boolean;
};

const controlCardStyle: CSSProperties = { ...cardStyle, marginBottom: "20px" };

export function ControlPanel({
  connectionState,
  licenseStatus,
  moduleConfigStatus,
  browserRuntimeStatus,
  browserRuntimeProgress,
  updaterStatus,
  availableUpdate,
  updateMessage,
  updateProgress,
  supportMessage,
  errorMessage,
  licenseKey,
  deviceName,
  excelPath,
  minScore,
  stopOnReview,
  isValidating,
  isStartingJob,
  isActivatingLicense,
  isBootstrappingBrowser,
  isCheckingUpdate,
  isInstallingUpdate,
  licenseBlocksStart,
  browserRuntimeBlocksStart,
  validationBlocksStart,
  onLicenseKeyChange,
  onDeviceNameChange,
  onExcelPathChange,
  onMinScoreChange,
  onStopOnReviewChange,
  onConnect,
  onRefreshJobs,
  onRefreshLicense,
  onSyncConfig,
  onValidate,
  onStartDryRun,
  onStartLive,
  onRefreshStatus,
  onPause,
  onResume,
  onCancel,
  onActivateLicense,
  onBrowseFile,
  onBootstrapBrowserRuntime,
  onReloadBrowserRuntime,
  onCheckForUpdates,
  onInstallUpdate,
  describeLicenseStatus,
  activeJobId,
  currentJobNeedsAuth,
}: ControlPanelProps) {
  return (
    <>
      <div
        style={{
          display: "flex",
          gap: "20px",
          alignItems: "flex-start",
          justifyContent: "space-between",
          flexWrap: "wrap",
          marginTop: "10px",
          marginBottom: "24px",
        }}
      >
        <div style={{ maxWidth: "760px" }}>
          <h1 style={{ marginTop: 0, marginBottom: "14px", fontSize: "38px" }}>
            {messages.app.title}
          </h1>
          <p style={{ lineHeight: 1.7, margin: 0 }}>{messages.app.description}</p>
        </div>
        <div
          style={{
            ...cardStyle,
            minWidth: "220px",
            backgroundColor:
              connectionState === "ready" ? "rgb(240, 253, 250)" : "rgba(255, 255, 255, 0.9)",
          }}
        >
          <div style={{ fontSize: "13px", color: "rgb(71, 85, 105)" }}>Sidecar</div>
          <div style={{ fontSize: "20px", fontWeight: 700, marginTop: "6px" }}>
            {connectionState === "ready"
              ? messages.app.connected
              : connectionState === "connecting"
                ? messages.app.connecting
                : connectionState}
          </div>
          {licenseStatus ? (
            <div style={{ marginTop: "10px", fontSize: "13px", color: "rgb(51, 65, 85)", lineHeight: 1.5 }}>
              <div>{messages.app.license.title}: {describeLicenseStatus(licenseStatus)}</div>
              <div>{messages.app.license.lastChecked}: {formatTimestamp(licenseStatus.last_checked_at)}</div>
            </div>
          ) : null}
          {moduleConfigStatus ? (
            <div style={{ marginTop: "10px", fontSize: "13px", color: "rgb(51, 65, 85)", lineHeight: 1.5 }}>
              <div>
                Config {moduleConfigStatus.version} ({moduleConfigStatus.source})
              </div>
              <div>
                Verify: {moduleConfigStatus.signature_verified ? "signed" : "bundled"}
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <section style={controlCardStyle}>
        <div style={{ display: "grid", gap: "12px" }}>
          <div
            style={{
              borderRadius: "12px",
              backgroundColor: licenseStatus?.configured ? "rgb(240, 253, 250)" : "rgb(255, 247, 237)",
              border: licenseStatus?.configured
                ? "1px solid rgb(167, 243, 208)"
                : "1px solid rgb(253, 186, 116)",
              padding: "12px 14px",
              display: "grid",
              gap: "10px",
            }}
          >
            <div style={{ fontWeight: 700 }}>License Activation</div>
            <div style={{ color: "rgb(51, 65, 85)" }}>
              {licenseStatus?.configured
                ? "เครื่องนี้ activate license แล้ว"
                : "ถ้ามี cloud แล้ว ยังไม่ activate จะเริ่ม job ใหม่ไม่ได้"}
            </div>
            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
              <input
                value={licenseKey}
                onChange={(event) => onLicenseKeyChange(event.target.value)}
                placeholder="DMC-XXXX-XXXX"
                style={{
                  flex: 1,
                  minWidth: "240px",
                  borderRadius: "12px",
                  border: "1px solid rgb(203, 213, 225)",
                  padding: "12px 14px",
                  fontSize: "15px",
                }}
              />
              <input
                value={deviceName}
                onChange={(event) => onDeviceNameChange(event.target.value)}
                placeholder="desktop-01"
                style={{
                  flex: 1,
                  minWidth: "220px",
                  borderRadius: "12px",
                  border: "1px solid rgb(203, 213, 225)",
                  padding: "12px 14px",
                  fontSize: "15px",
                }}
              />
              <button
                style={{ ...buttonStyle, backgroundColor: "rgb(22, 163, 74)" }}
                disabled={connectionState !== "ready" || isActivatingLicense}
                onClick={onActivateLicense}
              >
                Activate License
              </button>
            </div>
          </div>

          <label style={{ display: "grid", gap: "8px" }}>
            <span style={{ fontWeight: 600 }}>{messages.app.filePathLabel}</span>
            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
              <input
                value={excelPath}
                onChange={(event) => onExcelPathChange(event.target.value)}
                placeholder={messages.app.filePathPlaceholder}
                style={{
                  flex: 1,
                  minWidth: "360px",
                  borderRadius: "12px",
                  border: "1px solid rgb(203, 213, 225)",
                  padding: "12px 14px",
                  fontSize: "15px",
                }}
              />
              <button
                style={{ ...buttonStyle, backgroundColor: "rgb(3, 105, 161)" }}
                onClick={onBrowseFile}
              >
                {messages.app.browse}
              </button>
            </div>
          </label>

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "10px",
              alignItems: "center",
            }}
          >
            <button style={buttonStyle} onClick={onConnect}>
              {messages.app.connect}
            </button>
            <button
              style={{ ...buttonStyle, backgroundColor: "rgb(8, 145, 178)" }}
              onClick={onRefreshJobs}
            >
              {messages.app.refreshJobs}
            </button>
            <button
              style={{ ...buttonStyle, backgroundColor: "rgb(37, 99, 235)" }}
              onClick={onRefreshLicense}
            >
              {messages.app.license.refresh}
            </button>
            <button
              style={{ ...buttonStyle, backgroundColor: "rgb(2, 132, 199)" }}
              onClick={onSyncConfig}
            >
              {messages.app.syncConfig}
            </button>
            <button style={buttonStyle} disabled={isValidating} onClick={onValidate}>
              {messages.app.validate}
            </button>
            <button
              style={buttonStyle}
              disabled={
                isStartingJob ||
                isBootstrappingBrowser ||
                licenseBlocksStart ||
                browserRuntimeBlocksStart ||
                validationBlocksStart
              }
              onClick={onStartDryRun}
            >
              {messages.app.startDryRun}
            </button>
            <button
              style={{ ...buttonStyle, backgroundColor: "rgb(22, 163, 74)" }}
              disabled={
                isStartingJob ||
                isBootstrappingBrowser ||
                licenseBlocksStart ||
                browserRuntimeBlocksStart ||
                validationBlocksStart
              }
              onClick={onStartLive}
            >
              {messages.app.startLive}
            </button>
            <button
              style={{ ...buttonStyle, backgroundColor: "rgb(14, 116, 144)" }}
              disabled={!activeJobId}
              onClick={onRefreshStatus}
            >
              {messages.app.refreshStatus}
            </button>
            <button
              style={{ ...buttonStyle, backgroundColor: "rgb(100, 116, 139)" }}
              disabled={!activeJobId}
              onClick={onPause}
            >
              {messages.app.pause}
            </button>
            <button
              style={{ ...buttonStyle, backgroundColor: "rgb(217, 119, 6)" }}
              disabled={!currentJobNeedsAuth}
              onClick={onResume}
            >
              {messages.app.resume}
            </button>
            <button
              style={{ ...buttonStyle, backgroundColor: "rgb(220, 38, 38)" }}
              disabled={!activeJobId}
              onClick={onCancel}
            >
              {messages.app.cancel}
            </button>
          </div>

          <div style={{ display: "flex", gap: "20px", alignItems: "center", flexWrap: "wrap" }}>
            <label style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <span style={{ fontWeight: 600 }}>{messages.app.minScoreLabel}</span>
              <input
                type="number"
                min={0}
                max={100}
                value={minScore}
                onChange={(event) => onMinScoreChange(Number(event.target.value))}
                style={{
                  width: "90px",
                  borderRadius: "10px",
                  border: "1px solid rgb(203, 213, 225)",
                  padding: "8px 10px",
                }}
              />
            </label>
            <label style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <input
                type="checkbox"
                checked={stopOnReview}
                onChange={(event) => onStopOnReviewChange(event.target.checked)}
              />
              <span>{messages.app.stopOnReview}</span>
            </label>
          </div>

          <p style={{ margin: 0, color: "rgb(71, 85, 105)" }}>{messages.app.dryRunHint}</p>
          {validationBlocksStart ? (
            <p style={{ margin: 0, color: "rgb(180, 83, 9)", fontWeight: 600 }}>
              กรุณาตรวจไฟล์ Excel ให้ผ่านก่อนเริ่มงาน และตรวจใหม่ทุกครั้งหลังเปลี่ยนไฟล์
            </p>
          ) : null}
          <p style={{ margin: 0, color: "rgb(180, 83, 9)" }}>{messages.app.authHint}</p>

          {licenseStatus ? (
            <div
              style={{
                borderRadius: "12px",
                backgroundColor: licenseStatus.needs_attention ? "rgb(255, 247, 237)" : "rgb(240, 253, 250)",
                border: licenseStatus.needs_attention
                  ? "1px solid rgb(253, 186, 116)"
                  : "1px solid rgb(167, 243, 208)",
                color: licenseStatus.needs_attention ? "rgb(154, 52, 18)" : "rgb(6, 95, 70)",
                padding: "12px 14px",
              }}
            >
              <div>
                {messages.app.license.title}: {describeLicenseStatus(licenseStatus)}
              </div>
              <div>
                {messages.app.license.expiresAt}: {formatTimestamp(licenseStatus.expires_at)}
              </div>
              <div>
                {messages.app.license.offlineGraceUntil}: {formatTimestamp(licenseStatus.offline_grace_until)}
              </div>
              {licenseStatus.last_error ? (
                <div>
                  {messages.app.license.lastError}: {licenseStatus.last_error}
                </div>
              ) : null}
              {licenseStatus.offline_mode && licenseStatus.within_offline_grace ? (
                <div style={{ fontWeight: 700 }}>
                  อยู่ใน offline grace mode เริ่มงานได้ถึง {formatTimestamp(licenseStatus.offline_grace_until)}
                </div>
              ) : null}
            </div>
          ) : null}

          {moduleConfigStatus ? (
            <div
              style={{
                borderRadius: "12px",
                backgroundColor: moduleConfigStatus.last_error ? "rgb(255, 247, 237)" : "rgb(240, 249, 255)",
                border: moduleConfigStatus.last_error
                  ? "1px solid rgb(253, 186, 116)"
                  : "1px solid rgb(186, 230, 253)",
                color: moduleConfigStatus.last_error ? "rgb(154, 52, 18)" : "rgb(12, 74, 110)",
                padding: "12px 14px",
              }}
            >
              <div>
                {messages.app.configStatus}: {moduleConfigStatus.version} ({moduleConfigStatus.source})
              </div>
              <div>
                {messages.app.configCheckedAt}: {formatTimestamp(moduleConfigStatus.checked_at)}
              </div>
              <div>
                {messages.app.configSignature}:{" "}
                {moduleConfigStatus.signature_verified ? messages.app.configVerified : messages.app.configBundled}
              </div>
              {moduleConfigStatus.last_error ? (
                <div>
                  {messages.app.configFallback}: {moduleConfigStatus.last_error}
                </div>
              ) : null}
            </div>
          ) : null}

          {browserRuntimeStatus ? (
            <div
              style={{
                borderRadius: "12px",
                backgroundColor: browserRuntimeStatus.installed ? "rgb(240, 253, 250)" : "rgb(255, 247, 237)",
                border: browserRuntimeStatus.installed
                  ? "1px solid rgb(167, 243, 208)"
                  : "1px solid rgb(253, 186, 116)",
                color: browserRuntimeStatus.installed ? "rgb(6, 95, 70)" : "rgb(154, 52, 18)",
                padding: "12px 14px",
                display: "grid",
                gap: "8px",
              }}
            >
              <div style={{ fontWeight: 700 }}>Browser Runtime Setup</div>
              <div>{browserRuntimeStatus.message ?? "-"}</div>
              <div>State: {browserRuntimeStatus.state}</div>
              <div>Install dir: {browserRuntimeStatus.install_dir}</div>
              <div>Executable: {browserRuntimeStatus.executable_path ?? "-"}</div>
              <div>
                Estimated download: {formatBytes(browserRuntimeStatus.estimated_download_bytes)}
              </div>
              {browserRuntimeProgress ? (
                <div
                  style={{
                    borderRadius: "12px",
                    backgroundColor: "rgba(255,255,255,0.7)",
                    border: "1px solid rgba(148, 163, 184, 0.35)",
                    padding: "10px 12px",
                    display: "grid",
                    gap: "6px",
                  }}
                >
                  <div style={{ fontWeight: 700 }}>{describeBrowserRuntimePhase(browserRuntimeProgress.phase)}</div>
                  <div>{browserRuntimeProgress.message}</div>
                  {browserRuntimeProgress.percent !== null ? (
                    <div
                      style={{
                        height: "10px",
                        borderRadius: "999px",
                        backgroundColor: "rgb(226, 232, 240)",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          width: `${browserRuntimeProgress.percent}%`,
                          height: "100%",
                          background:
                            browserRuntimeProgress.phase === "failed"
                              ? "linear-gradient(90deg, rgb(248, 113, 113), rgb(239, 68, 68))"
                              : "linear-gradient(90deg, rgb(37, 99, 235), rgb(34, 197, 94))",
                        }}
                      />
                    </div>
                  ) : null}
                  {browserRuntimeProgress.detail ? <div>{browserRuntimeProgress.detail}</div> : null}
                </div>
              ) : null}
              {browserRuntimeStatus.required_components.length > 0 ? (
                <div style={{ display: "grid", gap: "4px" }}>
                  <div style={{ fontWeight: 700 }}>Installer plan</div>
                  {browserRuntimeStatus.required_components.map((component) => (
                    <div key={`${component.name}-${component.install_location}`}>
                      {component.name} • {formatBytes(component.download_bytes)}
                    </div>
                  ))}
                </div>
              ) : null}
              {browserRuntimeStatus.guidance ? <div>Guidance: {browserRuntimeStatus.guidance}</div> : null}
              {browserRuntimeStatus.last_error ? <div>Last error: {browserRuntimeStatus.last_error}</div> : null}
              {browserRuntimeStatus.log_tail.length > 0 ? (
                <div style={{ display: "grid", gap: "4px" }}>
                  <div style={{ fontWeight: 700 }}>Installer log tail</div>
                  {browserRuntimeStatus.log_tail.map((line, index) => (
                    <div key={`${line}-${index}`}>{line}</div>
                  ))}
                </div>
              ) : null}
              {!browserRuntimeStatus.installed ? (
                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                  <button
                    style={{ ...buttonStyle, backgroundColor: "rgb(37, 99, 235)" }}
                    disabled={
                      connectionState !== "ready" ||
                      isBootstrappingBrowser ||
                      !browserRuntimeStatus.bootstrap_supported
                    }
                    onClick={onBootstrapBrowserRuntime}
                  >
                    {isBootstrappingBrowser ? "Installing Chromium..." : "Install Chromium Runtime"}
                  </button>
                  <button
                    style={{ ...buttonStyle, backgroundColor: "rgb(8, 145, 178)" }}
                    disabled={connectionState !== "ready" || isBootstrappingBrowser}
                    onClick={onReloadBrowserRuntime}
                  >
                    Re-check Runtime
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}

          <div
            style={{
              borderRadius: "12px",
              backgroundColor: "rgb(248, 250, 252)",
              border: "1px solid rgb(226, 232, 240)",
              padding: "12px 14px",
              display: "grid",
              gap: "8px",
            }}
          >
            <div style={{ fontWeight: 700 }}>App Updates</div>
            <div>เวอร์ชันปัจจุบัน: {updaterStatus?.current_version ?? "-"}</div>
            <div>
              สถานะ updater: {updaterStatus?.configured ? "พร้อมใช้งาน" : "ยังไม่ตั้งค่า"}
            </div>
            <div>Endpoint: {updaterStatus?.endpoint ?? "-"}</div>
            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
              <button
                style={{ ...buttonStyle, backgroundColor: "rgb(79, 70, 229)" }}
                disabled={isCheckingUpdate}
                onClick={onCheckForUpdates}
              >
                เช็กอัปเดต
              </button>
              <button
                style={{ ...buttonStyle, backgroundColor: "rgb(124, 58, 237)" }}
                disabled={!availableUpdate || isInstallingUpdate}
                onClick={onInstallUpdate}
              >
                ติดตั้งอัปเดต
              </button>
            </div>
            {availableUpdate ? (
              <div style={{ color: "rgb(51, 65, 85)", lineHeight: 1.6 }}>
                <div>พบเวอร์ชันใหม่: {availableUpdate.version}</div>
                <div>เผยแพร่เมื่อ: {formatTimestamp(availableUpdate.date)}</div>
                <div>รายละเอียด: {availableUpdate.body ?? "-"}</div>
              </div>
            ) : null}
            {updateProgress ? (
              <div style={{ color: "rgb(51, 65, 85)" }}>
                ดาวน์โหลดแล้ว {updateProgress.downloaded}
                {updateProgress.contentLength ? ` / ${updateProgress.contentLength}` : ""} bytes
              </div>
            ) : null}
            {updateMessage ? <div style={{ color: "rgb(51, 65, 85)" }}>{updateMessage}</div> : null}
            {supportMessage ? <div style={{ color: "rgb(15, 23, 42)" }}>{supportMessage}</div> : null}
          </div>

          {errorMessage ? (
            <div
              style={{
                borderRadius: "12px",
                backgroundColor: "rgb(254, 242, 242)",
                border: "1px solid rgb(254, 202, 202)",
                color: "rgb(153, 27, 27)",
                padding: "12px 14px",
              }}
            >
              {errorMessage}
            </div>
          ) : null}
        </div>
      </section>
    </>
  );
}
