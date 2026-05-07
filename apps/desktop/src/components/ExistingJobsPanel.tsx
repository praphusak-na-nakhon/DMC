import { useMemo, useState } from "react";
import { FolderOpen, PlayCircle, RotateCcw, Search, Trash2 } from "lucide-react";
import messages from "../i18n/th.json";
import { describeJobStatus, formatTimestamp } from "../lib/appUi";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import type { JobStatusSnapshot } from "../types/contracts";

type ExistingJobsPanelProps = {
  existingJobs: JobStatusSnapshot[];
  activeJobId: string | null;
  isStartingJob: boolean;
  isArchivingJobs?: boolean;
  onSelectJob: (job: JobStatusSnapshot) => void;
  onResumeExisting: (job: JobStatusSnapshot) => void;
  onRevealPath: (path: string) => void;
  onArchiveOldJobs?: () => void;
};

function jobBadgeClass(status: string) {
  if (status === "failed" || status === "cancelled") return "border-destructive/30 bg-destructive/15 text-destructive";
  return "border-border bg-secondary text-secondary-foreground";
}

export function ExistingJobsPanel({
  existingJobs,
  activeJobId,
  isStartingJob,
  isArchivingJobs = false,
  onSelectJob,
  onResumeExisting,
  onRevealPath,
  onArchiveOldJobs,
}: ExistingJobsPanelProps) {
  const [statusFilter, setStatusFilter] = useState<"latest" | "active" | "done" | "failed" | "all">("latest");
  const visibleJobs = useMemo(() => {
    if (statusFilter === "latest") return existingJobs.slice(0, 20);
    if (statusFilter === "all") return existingJobs.slice(0, 20);
    if (statusFilter === "active") {
      return existingJobs.filter((job) =>
        ["running", "paused", "stopped_on_review", "failed"].includes(job.status),
      ).slice(0, 20);
    }
    if (statusFilter === "done") return existingJobs.filter((job) => job.status === "done").slice(0, 20);
    return existingJobs.filter((job) => job.status === "failed").slice(0, 20);
  }, [existingJobs, statusFilter]);

  return (
    <Card className="min-w-0">
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CardTitle>{messages.app.existingJobs.title}</CardTitle>
            <CardDescription>{messages.app.existingJobs.description}</CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}
              className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="latest">{messages.app.existingJobs.latest20}</option>
              <option value="active">{messages.app.existingJobs.filterActive}</option>
              <option value="done">{messages.app.existingJobs.filterDone}</option>
              <option value="failed">{messages.app.existingJobs.filterFailed}</option>
              <option value="all">{messages.app.existingJobs.filterAll}</option>
            </select>
            {onArchiveOldJobs ? (
              <Button
                size="sm"
                variant="outline"
                disabled={isArchivingJobs || existingJobs.length <= 20}
                onClick={onArchiveOldJobs}
              >
                {isArchivingJobs ? <RotateCcw className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                {messages.app.existingJobs.archiveOld}
              </Button>
            ) : null}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {existingJobs.length > 0 ? (
          <div className="panel-scroll grid max-h-[680px] gap-3 overflow-auto pr-1">
            {visibleJobs.length === 0 ? (
              <div className="rounded-lg border border-dashed bg-muted/30 p-4 text-sm text-muted-foreground">
                {messages.app.existingJobs.emptyFiltered}
              </div>
            ) : null}
            {visibleJobs.map((job) => {
              const reportPath = job.report_path;
              const reviewReportPath = job.review_report_path;
              const reportDirectory = reportPath?.replace(/[\\/][^\\/]+$/, "") ?? reviewReportPath?.replace(/[\\/][^\\/]+$/, "");
              const isActive = activeJobId === job.job_id;
              return (
                <div
                  key={job.job_id}
                  className={`min-w-0 rounded-lg border p-3 ${isActive ? "bg-muted" : "bg-card"}`}
                >
                  <div className="flex min-w-0 items-start justify-between gap-2">
                    <div className="min-w-0 truncate font-semibold">{job.job_id}</div>
                    <Badge variant="outline" className={jobBadgeClass(job.status)}>
                      {describeJobStatus(job.status)}
                    </Badge>
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    {job.level_label ?? "-"} - {job.processed}/{job.total ?? "-"}
                  </div>
                  {job.run_summary ? (
                    <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                      <div className="rounded-md border bg-muted/30 p-2">
                        <div>DMC rows</div>
                        <div className="font-semibold text-foreground">{job.run_summary.dmc_rows_total}</div>
                      </div>
                      <div className="rounded-md border bg-muted/30 p-2">
                        <div>Excel ไม่พบใน DMC</div>
                        <div className="font-semibold text-foreground">{job.run_summary.excel_missing}</div>
                      </div>
                      <div className="rounded-md border bg-muted/30 p-2">
                        <div>matched</div>
                        <div className="font-semibold text-foreground">{job.run_summary.matched_from_excel}</div>
                      </div>
                      <div className="rounded-md border bg-muted/30 p-2">
                        <div>default 207</div>
                        <div className="font-semibold text-foreground">{job.run_summary.default_207}</div>
                      </div>
                    </div>
                  ) : null}
                  <div className="mt-2 grid gap-1 text-xs text-muted-foreground">
                    <div className="break-words">
                      <span className="font-semibold text-foreground">{messages.app.existingJobs.sourceFile}:</span>{" "}
                      {job.source_file}
                    </div>
                    <div>
                      <span className="font-semibold text-foreground">{messages.app.existingJobs.updatedAt}:</span>{" "}
                      {formatTimestamp(job.finished_at ?? job.started_at)}
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" onClick={() => onSelectJob(job)}>
                      <Search className="h-4 w-4" />
                      ใช้งานรายการนี้
                    </Button>
                    <Button
                      size="sm"
                      disabled={isStartingJob || job.status === "done" || job.status === "cancelled"}
                      onClick={() => onResumeExisting(job)}
                    >
                      <RotateCcw className="h-4 w-4" />
                      {messages.app.resumeExisting}
                    </Button>
                    {reportPath ? (
                      <Button size="sm" variant="outline" onClick={() => onRevealPath(reportPath)}>
                        <PlayCircle className="h-4 w-4" />
                        {messages.app.progress.openReport}
                      </Button>
                    ) : null}
                    {reviewReportPath ? (
                      <Button size="sm" variant="outline" onClick={() => onRevealPath(reviewReportPath)}>
                        <Search className="h-4 w-4" />
                        เปิด review
                      </Button>
                    ) : null}
                    {reportDirectory ? (
                      <Button size="sm" variant="outline" onClick={() => onRevealPath(reportDirectory)}>
                        <FolderOpen className="h-4 w-4" />
                        โฟลเดอร์
                      </Button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed bg-muted/30 p-6 text-center text-sm text-muted-foreground">
            {messages.app.existingJobs.empty}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
