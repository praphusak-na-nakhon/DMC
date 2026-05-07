import { AlertCircle, CheckCircle2, ExternalLink, FileText, FolderOpen, Loader2 } from "lucide-react";
import messages from "../i18n/th.json";
import { describeJobStatus } from "../lib/appUi";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Progress } from "./ui/progress";
import type { JobStatusSnapshot } from "../types/contracts";

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

export function JobProgressPanel({ currentJob, progressPercent, onRevealPath }: JobProgressPanelProps) {
  const reportPath = currentJob?.report_path ?? null;
  const reviewReportPath = currentJob?.review_report_path ?? null;
  const runSummary = currentJob?.run_summary ?? null;
  const processedLabel =
    currentJob?.total !== null && currentJob?.total !== undefined && currentJob.processed > currentJob.total
      ? `${currentJob.processed} แถวบนเว็บ (Excel validate ${currentJob.total} รายการ)`
      : `${currentJob?.processed ?? 0}/${currentJob?.total ?? "-"}`;
  const reportDirectory = reportPath?.replace(/[\\/][^\\/]+$/, "") ?? reviewReportPath?.replace(/[\\/][^\\/]+$/, "");

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
            </div>

            {reportPath || reviewReportPath ? (
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
                  ต้อง login DMC แล้วกด Resume
                </div>
                <div className="mt-1 text-muted-foreground">reason: {currentJob.auth_reason ?? "auth_required"}</div>
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
