import { AlertCircle, CheckCircle2, ExternalLink, FileSpreadsheet, FileText, FolderOpen, Loader2 } from "lucide-react";
import messages from "../i18n/th.json";
import { describeJobStatus } from "../lib/appUi";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Progress } from "./ui/progress";
import type { JobCompletionItem, JobStatusSnapshot } from "../types/contracts";

type JobProgressPanelProps = {
  currentJob: JobStatusSnapshot | null;
  progressPercent: number;
  onRevealPath: (path: string) => void;
};

const activeStatuses = new Set(["running", "paused", "stopped_on_review"]);

function statusBadgeClass(status: string) {
  if (status === "failed" || status === "cancelled") return "border-destructive/30 bg-destructive/15 text-destructive";
  return "border-border bg-secondary text-secondary-foreground";
}

function describeAuthReason(reason: string | null) {
  if (reason === "dmc_login_rejected") {
    return "DMC ปฏิเสธการเข้าใช้จาก ThaiD นี้ หรือบัญชียังไม่ได้ลงทะเบียน/อนุมัติใน DMC";
  }
  if (reason === "dmc_transfer_form_unavailable") {
    return "login DMC แล้ว แต่ระบบยังเปิดหน้าฟอร์มย้ายเข้าไม่ได้ ให้ตรวจสิทธิ์เมนู 2.7.1 ใน Chromium";
  }
  if (reason === "session_expired" || reason === "session_expired_during_submit") {
    return "session DMC หมดอายุ ต้อง login ใหม่ใน Chromium แล้วกด Resume";
  }
  return "ต้อง login DMC ให้สำเร็จใน Chromium แล้วกด Resume";
}

function completionItemLabel(item: JobCompletionItem) {
  return item.full_name ?? item.student_no ?? item.citizen_id ?? item.record_id ?? `row ${item.row_index ?? "-"}`;
}

function completionItemMeta(item: JobCompletionItem) {
  return [
    item.student_no ? `เลขประจำตัว ${item.student_no}` : null,
    item.classroom ? `ห้อง ${item.classroom}` : null,
    item.note ?? item.status,
  ]
    .filter(Boolean)
    .join(" / ");
}

function CompletionList({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: JobCompletionItem[];
  emptyText: string;
}) {
  const visibleItems = items.slice(0, 8);
  return (
    <div className="rounded-md border bg-background p-3">
      <div className="font-semibold">{title}</div>
      {visibleItems.length > 0 ? (
        <ul className="mt-2 space-y-2">
          {visibleItems.map((item, index) => (
            <li key={`${item.record_id ?? item.student_no ?? item.row_index ?? index}-${index}`} className="min-w-0">
              <div className="truncate font-medium">{completionItemLabel(item)}</div>
              <div className="truncate text-xs text-muted-foreground">{completionItemMeta(item)}</div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-2 text-sm text-muted-foreground">{emptyText}</div>
      )}
      {items.length > visibleItems.length ? (
        <div className="mt-2 text-xs text-muted-foreground">และอีก {items.length - visibleItems.length} คนในไฟล์ Excel</div>
      ) : null}
    </div>
  );
}

function stoppedReason(job: JobStatusSnapshot) {
  const reason = job.stopped_item?.reason;
  return typeof reason === "string" ? reason : null;
}

export function JobProgressPanel({ currentJob, progressPercent, onRevealPath }: JobProgressPanelProps) {
  const reportPath = currentJob?.report_path ?? null;
  const reviewReportPath = currentJob?.review_report_path ?? null;
  const summaryReportPath = currentJob?.summary_report_path ?? null;
  const runSummary = currentJob?.run_summary ?? null;
  const completionSummary = currentJob?.completion_summary ?? null;
  const processedLabel =
    currentJob?.total !== null && currentJob?.total !== undefined && currentJob.processed > currentJob.total
      ? `${currentJob.processed} แถวบนเว็บ (Excel validate ${currentJob.total} รายการ)`
      : `${currentJob?.processed ?? 0}/${currentJob?.total ?? "-"}`;
  const reportDirectory =
    reportPath?.replace(/[\\/][^\\/]+$/, "") ??
    reviewReportPath?.replace(/[\\/][^\\/]+$/, "") ??
    summaryReportPath?.replace(/[\\/][^\\/]+$/, "");

  return (
    <Card className="min-w-0">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>{messages.app.progress.title}</CardTitle>
            <CardDescription>สถานะงานล่าสุดและไฟล์รายงานหลังจบงาน</CardDescription>
          </div>
          {currentJob ? (
            <Badge variant="outline" className={statusBadgeClass(currentJob.status)}>
              {describeJobStatus(currentJob.status)}
            </Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="min-w-0">
        {currentJob ? (
          <div className="space-y-4">
            <div className="space-y-2">
              <Progress value={progressPercent} className="h-3" />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{messages.app.progress.processed}: {processedLabel}</span>
                <span>{Math.round(progressPercent)}%</span>
              </div>
            </div>

            <div className="grid gap-2 sm:grid-cols-3">
              <div className="rounded-lg border bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground">{messages.app.progress.currentPage}</div>
                <div className="mt-1 text-lg font-semibold">{currentJob.current_page ?? "-"}</div>
              </div>
              <div className="rounded-lg border bg-muted/40 p-3">
                <div className="text-xs">{messages.app.progress.success}</div>
                <div className="mt-1 text-lg font-semibold">{currentJob.succeeded}</div>
              </div>
              <div className="rounded-lg border bg-muted/40 p-3">
                <div className="text-xs">{messages.app.progress.failed}</div>
                <div className="mt-1 text-lg font-semibold">{currentJob.failed}</div>
              </div>
            </div>

            {runSummary ? (
              <div className="space-y-2 rounded-lg border bg-muted/25 p-3">
                <div>
                  <div className="font-semibold">สรุปผลรันล่าสุด</div>
                  <div className="text-xs text-muted-foreground">
                    เทียบแถวที่อ่านจาก DMC กับข้อมูลที่รับจาก Excel
                  </div>
                </div>
                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs text-muted-foreground">DMC rows ทั้งหมด</div>
                    <div className="mt-1 text-xl font-semibold">{runSummary.dmc_rows_total}</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs text-muted-foreground">matched จาก Excel</div>
                    <div className="mt-1 text-xl font-semibold">{runSummary.matched_from_excel}</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs text-muted-foreground">default 207</div>
                    <div className="mt-1 text-xl font-semibold">{runSummary.default_207}</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs text-muted-foreground">Excel ไม่พบใน DMC</div>
                    <div className="mt-1 text-xl font-semibold">{runSummary.excel_missing}</div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span>ต้อง review: {runSummary.review_rows}</span>
                  <span>เขียนจริง: {runSummary.applied_rows}</span>
                  <span>dry run: {runSummary.dry_run_rows}</span>
                </div>
              </div>
            ) : null}

            {completionSummary ? (
              <div className="space-y-3 rounded-lg border bg-muted/25 p-3">
                <div>
                  <div className="font-semibold">สรุปผลกรอกข้อมูล</div>
                  <div className="text-xs text-muted-foreground">รวม {completionSummary.total} คน</div>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs text-muted-foreground">สำเร็จ</div>
                    <div className="mt-1 text-xl font-semibold">{completionSummary.succeeded}</div>
                  </div>
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs text-muted-foreground">ล้มเหลว/ต้องตรวจ</div>
                    <div className="mt-1 text-xl font-semibold">{completionSummary.failed}</div>
                  </div>
                </div>
                <div className="grid gap-3 lg:grid-cols-2">
                  <CompletionList
                    title="รายชื่อที่สำเร็จ"
                    items={completionSummary.success_items}
                    emptyText="ยังไม่มีรายการสำเร็จ"
                  />
                  <CompletionList
                    title="รายชื่อที่ล้มเหลว/ต้องตรวจ"
                    items={completionSummary.failure_items}
                    emptyText="ไม่มีรายการล้มเหลว"
                  />
                </div>
              </div>
            ) : null}

            <div className="grid gap-2 text-sm">
              <div className="break-words">
                <span className="font-semibold">ไฟล์:</span> {currentJob.source_file}
              </div>
              <div className="break-words">
                <span className="font-semibold">Report:</span> {reportPath ?? "-"}
              </div>
              <div className="break-words">
                <span className="font-semibold">Review:</span> {reviewReportPath ?? "-"}
              </div>
              <div className="break-words">
                <span className="font-semibold">Summary Excel:</span> {summaryReportPath ?? "-"}
              </div>
            </div>

            {reportPath || reviewReportPath || summaryReportPath ? (
              <div className="flex flex-wrap gap-2">
                {reportPath ? (
                  <Button size="sm" onClick={() => onRevealPath(reportPath)}>
                    <FileText className="h-4 w-4" />
                    {messages.app.progress.openReport}
                  </Button>
                ) : null}
                {reportDirectory ? (
                  <Button size="sm" variant="outline" onClick={() => onRevealPath(reportDirectory)}>
                    <FolderOpen className="h-4 w-4" />
                    {messages.app.progress.openReportFolder}
                  </Button>
                ) : null}
                {summaryReportPath ? (
                  <Button size="sm" variant="outline" onClick={() => onRevealPath(summaryReportPath)}>
                    <FileSpreadsheet className="h-4 w-4" />
                    เปิดสรุป Excel
                  </Button>
                ) : null}
                {reviewReportPath ? (
                  <Button size="sm" variant="outline" onClick={() => onRevealPath(reviewReportPath)}>
                    <ExternalLink className="h-4 w-4" />
                    เปิด review
                  </Button>
                ) : null}
              </div>
            ) : null}

            {currentJob.needs_auth ? (
              <div className="rounded-lg border bg-muted/40 p-3 text-sm">
                <div className="flex items-center gap-2 font-semibold">
                  <AlertCircle className="h-4 w-4" />
                  {describeAuthReason(currentJob.auth_reason)}
                </div>
                <div className="mt-1 text-muted-foreground">reason: {currentJob.auth_reason ?? "auth_required"}</div>
              </div>
            ) : currentJob.status === "paused" && stoppedReason(currentJob) === "dry_run_review" ? (
              <div className="rounded-lg border bg-muted/40 p-3 text-sm">
                <div className="flex items-center gap-2 font-semibold">
                  <AlertCircle className="h-4 w-4" />
                  Dry run กรอกครบแล้ว Chromium ถูกค้างไว้ให้ตรวจสอบ
                </div>
                <div className="mt-1 text-muted-foreground">ตรวจหน้า Chromium แล้วกด Resume เพื่อปิด browser และเขียน report</div>
              </div>
            ) : currentJob.status === "done" ? (
              <div className="rounded-lg border bg-muted/40 p-3 text-sm">
                <div className="flex items-center gap-2 font-semibold">
                  <CheckCircle2 className="h-4 w-4" />
                  งานเสร็จแล้ว ตรวจ report เพื่อปิดรอบงาน
                </div>
              </div>
            ) : activeStatuses.has(currentJob.status) ? (
              <div className="rounded-lg border bg-muted/35 p-3 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  กำลังติดตามสถานะจาก sidecar
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed bg-muted/30 p-6 text-center text-sm text-muted-foreground">
            {messages.app.progress.empty}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
