import { useMemo, useState } from "react";
import { FolderOpen, PlayCircle, RotateCcw, Search } from "lucide-react";
import messages from "../i18n/th.json";
import { formatTimestamp } from "../lib/appUi";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import type { JobStatusSnapshot } from "../types/contracts";

type ExistingJobsPanelProps = {
  existingJobs: JobStatusSnapshot[];
  activeJobId: string | null;
  isStartingJob: boolean;
  onSelectJob: (job: JobStatusSnapshot) => void;
  onResumeExisting: (job: JobStatusSnapshot) => void;
  onRevealPath: (path: string) => void;
};

function jobBadgeClass(status: string) {
  if (status === "failed" || status === "cancelled") return "border-destructive/30 bg-destructive/15 text-destructive";
  return "border-border bg-secondary text-secondary-foreground";
}

export function ExistingJobsPanel({
  existingJobs,
  activeJobId,
  isStartingJob,
  onSelectJob,
  onResumeExisting,
  onRevealPath,
}: ExistingJobsPanelProps) {
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "done" | "failed">("active");
  const visibleJobs = useMemo(() => {
    if (statusFilter === "all") return existingJobs;
    if (statusFilter === "active") {
      return existingJobs.filter((job) =>
        ["running", "paused", "stopped_on_review", "failed"].includes(job.status),
      );
    }
    if (statusFilter === "done") return existingJobs.filter((job) => job.status === "done");
    return existingJobs.filter((job) => job.status === "failed");
  }, [existingJobs, statusFilter]);

  return (
    <Card className="min-w-0">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>{messages.app.existingJobs.title}</CardTitle>
            <CardDescription>กลับมาทำงานต่อหรือเปิดรายงานย้อนหลัง</CardDescription>
          </div>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}
            className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="active">{messages.app.existingJobs.filterActive}</option>
            <option value="done">{messages.app.existingJobs.filterDone}</option>
            <option value="failed">{messages.app.existingJobs.filterFailed}</option>
            <option value="all">{messages.app.existingJobs.filterAll}</option>
          </select>
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
                      {job.status}
                    </Badge>
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    {job.level_label ?? "-"} - {job.processed}/{job.total ?? "-"}
                  </div>
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
