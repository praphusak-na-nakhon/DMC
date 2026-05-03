import {
  AlertTriangle,
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  FileCheck2,
  FileSearch,
  FolderOpen,
  Loader2,
  RefreshCw,
  UploadCloud,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { addPsarEvidence, generatePsarReport, getPsarReadiness, openEvidenceDialog } from "../lib/rpcClient";
import type {
  PsarEvidenceMapping,
  PsarReadinessRequirement,
  PsarReadinessResponse,
  ReadinessPriority,
  ReadinessRequirementStatus,
} from "../types/contracts";
import { Alert, AlertDescription } from "./ui/alert";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Progress } from "./ui/progress";

type PsarReadinessPageProps = {
  onBackHome: () => void;
  onRevealPath: (path: string) => void;
};

function percent(value: number): number {
  return Math.round(Math.max(0, Math.min(1, value)) * 100);
}

function statusVariant(status: ReadinessRequirementStatus): "default" | "secondary" | "destructive" | "outline" {
  if (status === "complete") {
    return "default";
  }
  if (status === "missing") {
    return "destructive";
  }
  if (status === "needs_review") {
    return "secondary";
  }
  return "outline";
}

function priorityVariant(priority: ReadinessPriority): "default" | "secondary" | "destructive" | "outline" {
  if (priority === "high") {
    return "destructive";
  }
  if (priority === "medium") {
    return "secondary";
  }
  return "outline";
}

function statusLabel(status: ReadinessRequirementStatus): string {
  if (status === "needs_review") {
    return "Needs review";
  }
  return status[0].toUpperCase() + status.slice(1);
}

function readableError(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error);
  const code = raw.match(/[A-Z][A-Z0-9_]+/)?.[0] ?? raw;
  const messages: Record<string, string> = {
    PSAR_EVIDENCE_FILE_NOT_FOUND: "Evidence file was not found.",
    PSAR_EVIDENCE_PATH_NOT_FILE: "Selected evidence path is not a file.",
    PSAR_EVIDENCE_UNSUPPORTED_TYPE: "Evidence must be PDF, DOCX, XLSX, or image.",
    PSAR_PROJECT_ID_INVALID: "Project ID can use only letters, numbers, dash, underscore, and dot.",
  };
  return messages[code] ?? raw;
}

export function PsarReadinessPage({ onBackHome, onRevealPath }: PsarReadinessPageProps) {
  const [projectId, setProjectId] = useState("default");
  const [evidencePath, setEvidencePath] = useState("");
  const [readiness, setReadiness] = useState<PsarReadinessResponse | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [isAddingEvidence, setIsAddingEvidence] = useState(false);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [generationNotice, setGenerationNotice] = useState<string | null>(null);
  const [reportPath, setReportPath] = useState<string | null>(null);

  const loadReadiness = useCallback(async (targetProjectId: string) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const response = await getPsarReadiness(targetProjectId.trim() || "default");
      setReadiness(response);
      setGenerationNotice(null);
      setReportPath(null);
    } catch (error) {
      setErrorMessage(readableError(error));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadReadiness("default");
  }, [loadReadiness]);

  const summaryCards = useMemo(() => {
    if (!readiness) {
      return [
        ["Complete", "-"],
        ["Partial", "-"],
        ["Missing", "-"],
        ["Needs Review", "-"],
      ] as const;
    }
    return [
      ["Complete", readiness.complete_count],
      ["Partial", readiness.partial_count],
      ["Missing", readiness.missing_count],
      ["Needs Review", readiness.needs_review_count],
    ] as const;
  }, [readiness]);

  const filePathById = useMemo(() => {
    const entries = readiness?.uploaded_files.map((file) => [file.file_id, file.file_path] as const) ?? [];
    return new Map(entries);
  }, [readiness]);

  const belowThreshold =
    readiness !== null && readiness.overall_completion_score < readiness.warning_threshold;

  async function handleBrowseEvidence(autoAdd = false) {
    try {
      const selected = await openEvidenceDialog();
      if (!selected) {
        return;
      }
      setEvidencePath(selected);
      setErrorMessage(null);
      setNotice(null);
      if (autoAdd) {
        await addEvidencePath(selected);
      }
    } catch (error) {
      setErrorMessage(readableError(error));
    }
  }

  async function addEvidencePath(path: string) {
    const selectedPath = path.trim();
    if (!selectedPath) {
      setErrorMessage("Choose an evidence file first.");
      return;
    }
    setIsAddingEvidence(true);
    setErrorMessage(null);
    setNotice(null);
    try {
      const response = await addPsarEvidence(projectId.trim() || "default", selectedPath);
      setReadiness(response.readiness);
      setGenerationNotice(null);
      setReportPath(null);
      setNotice(
        response.mappings.length
          ? `Evidence found: ${response.mappings.length} mapping(s) from ${response.file.file_name}.`
          : `No clear P-SAR mapping found for ${response.file.file_name}. The file is saved for review.`,
      );
    } catch (error) {
      setErrorMessage(readableError(error));
    } finally {
      setIsAddingEvidence(false);
    }
  }

  function toggleRequirement(requirementId: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(requirementId)) {
        next.delete(requirementId);
      } else {
        next.add(requirementId);
      }
      return next;
    });
  }

  async function handleGenerateReport() {
    if (!readiness) {
      return;
    }
    if (
      belowThreshold &&
      typeof window !== "undefined" &&
      !window.confirm(
        `Readiness is ${percent(readiness.overall_completion_score)}%, below the ${percent(readiness.warning_threshold)}% warning threshold. Generate the official P-SAR form anyway? Missing fields may remain blank.`,
      )
    ) {
      return;
    }

    setIsGeneratingReport(true);
    setErrorMessage(null);
    setGenerationNotice(null);
    try {
      const response = await generatePsarReport(projectId.trim() || "default");
      setReadiness(response.readiness);
      setReportPath(response.report_path);
      setGenerationNotice(`Generated official P-SAR form from template: ${response.report_path}`);
    } catch (error) {
      setErrorMessage(readableError(error));
    } finally {
      setIsGeneratingReport(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 border-b pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <Button variant="outline" size="sm" onClick={onBackHome}>
            <ArrowLeft className="h-4 w-4" />
            Back home
          </Button>
          <div className="mt-5 flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg border bg-background">
              <FileSearch className="h-6 w-6 text-primary" />
            </div>
            <div>
              <Badge variant="default">Assistant dashboard</Badge>
              <h1 className="mt-2 text-3xl font-bold tracking-normal">P-SAR Readiness</h1>
              <p className="mt-2 max-w-3xl text-muted-foreground">
                Evidence found here is a preparation signal, not an official approval of the final report.
              </p>
            </div>
          </div>
        </div>
      </header>

      {errorMessage ? (
        <Alert variant="destructive">
          <AlertDescription>{errorMessage}</AlertDescription>
        </Alert>
      ) : null}

      {notice ? (
        <Alert>
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card>
          <CardHeader>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <CardTitle>Your report is {readiness ? percent(readiness.overall_completion_score) : 0}% ready</CardTitle>
                <CardDescription>
                  Some required evidence may still be missing. Upload the recommended files below to improve report completeness.
                </CardDescription>
              </div>
              {isLoading ? <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /> : null}
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            <Progress value={readiness ? percent(readiness.overall_completion_score) : 0} className="h-3" />
            <div className="grid gap-3 sm:grid-cols-4">
              {summaryCards.map(([label, value]) => (
                <div key={label} className="rounded-lg border bg-muted/40 p-3">
                  <div className="text-xs text-muted-foreground">{label}</div>
                  <div className="mt-1 text-2xl font-bold">{value}</div>
                </div>
              ))}
            </div>
            {belowThreshold ? (
              <div className="flex flex-col gap-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    Readiness is below {percent(readiness.warning_threshold)}%. The official form can be generated, but missing fields may remain blank.
                  </span>
                </div>
                <Button variant="outline" size="sm" disabled={isGeneratingReport} onClick={() => void handleGenerateReport()}>
                  {isGeneratingReport ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileCheck2 className="h-4 w-4" />}
                  Generate anyway
                </Button>
              </div>
            ) : null}
            {!belowThreshold ? (
              <Button disabled={!readiness || isGeneratingReport} onClick={() => void handleGenerateReport()}>
                {isGeneratingReport ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileCheck2 className="h-4 w-4" />}
                Generate official P-SAR form
              </Button>
            ) : null}
            {generationNotice ? (
              <div className="flex flex-col gap-3 rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground lg:flex-row lg:items-center lg:justify-between">
                <span className="break-words">{generationNotice}</span>
                {reportPath ? (
                  <Button variant="outline" size="sm" onClick={() => onRevealPath(reportPath)}>
                    <FileCheck2 className="h-4 w-4" />
                    Open report
                  </Button>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Upload evidence</CardTitle>
            <CardDescription>Supported files: PDF, DOCX, XLSX, and images.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-2">
              <Label>Project ID</Label>
              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                <Input value={projectId} onChange={(event) => setProjectId(event.target.value)} />
                <Button variant="outline" disabled={isLoading} onClick={() => void loadReadiness(projectId)}>
                  {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  Load
                </Button>
              </div>
            </div>
            <div className="grid gap-2">
              <Label>Evidence file</Label>
              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                <Input value={evidencePath} onChange={(event) => setEvidencePath(event.target.value)} placeholder="C:\\dmc\\lesson-plan.docx" />
                <Button variant="outline" disabled={isAddingEvidence} onClick={() => void handleBrowseEvidence()}>
                  <FolderOpen className="h-4 w-4" />
                  Browse
                </Button>
              </div>
            </div>
            <Button disabled={!evidencePath.trim() || isAddingEvidence} onClick={() => void addEvidencePath(evidencePath)}>
              {isAddingEvidence ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
              Upload missing evidence
            </Button>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-4">
          {readiness?.sections.map((section) => (
            <Card key={section.section_id}>
              <CardHeader>
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <CardTitle>{section.section_title}</CardTitle>
                    <CardDescription>{percent(section.completion_score)}% complete</CardDescription>
                  </div>
                  <Badge variant="outline">
                    {section.complete_count} complete / {section.requirements.length} requirements
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {section.requirements.map((requirement) => (
                  <RequirementRow
                    key={requirement.requirement_id}
                    requirement={requirement}
                    expanded={expanded.has(requirement.requirement_id)}
                    onToggle={() => toggleRequirement(requirement.requirement_id)}
                    filePathById={filePathById}
                    onRevealPath={onRevealPath}
                  />
                ))}
              </CardContent>
            </Card>
          ))}
        </div>

        <aside className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recommended uploads</CardTitle>
              <CardDescription>Sorted by priority from the P-SAR requirement matrix.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {readiness && readiness.missing_evidence_recommendations.length === 0 ? (
                <div className="rounded-lg border bg-muted/40 p-3 text-sm text-muted-foreground">
                  No recommended upload is currently missing.
                </div>
              ) : null}
              {readiness?.missing_evidence_recommendations.slice(0, 12).map((item) => (
                <div key={`${item.requirement_id}-${item.evidence_name}`} className="rounded-lg border p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="font-semibold leading-6">{item.evidence_name}</div>
                    <Badge variant={priorityVariant(item.priority)}>{item.priority}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">{item.section_title}</div>
                  <div className="mt-2 text-sm leading-6 text-muted-foreground">{item.why_needed}</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.suggested_file_types.map((fileType) => (
                      <Badge key={fileType} variant="outline">{fileType}</Badge>
                    ))}
                  </div>
                  <Button className="mt-3 w-full" variant="outline" size="sm" onClick={() => void handleBrowseEvidence(true)}>
                    <UploadCloud className="h-4 w-4" />
                    Upload evidence
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Mapped files</CardTitle>
              <CardDescription>Files currently mapped to P-SAR requirements.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {readiness && readiness.mapped_files.length === 0 ? (
                <div className="rounded-lg border bg-muted/40 p-3 text-sm text-muted-foreground">
                  No mapped files yet.
                </div>
              ) : null}
              {readiness?.mapped_files.slice(0, 12).map((mapping) => (
                <MappedFile key={`${mapping.requirement_id}-${mapping.source_file_id}-${mapping.evidence_type}`} mapping={mapping} />
              ))}
              {readiness && readiness.uploaded_files.length > readiness.mapped_files.length ? (
                <div className="text-xs text-muted-foreground">
                  {readiness.uploaded_files.length} uploaded file(s), including files with no clear mapping.
                </div>
              ) : null}
            </CardContent>
          </Card>
        </aside>
      </section>
    </div>
  );
}

function RequirementRow({
  requirement,
  expanded,
  onToggle,
  filePathById,
  onRevealPath,
}: {
  requirement: PsarReadinessRequirement;
  expanded: boolean;
  onToggle: () => void;
  filePathById: Map<string, string>;
  onRevealPath: (path: string) => void;
}) {
  return (
    <div className="rounded-lg border">
      <button
        type="button"
        className="grid w-full gap-3 p-3 text-left lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center"
        aria-expanded={expanded}
        onClick={onToggle}
      >
        <div className="flex min-w-0 gap-3">
          <div className="mt-1 shrink-0">
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </div>
          <div className="min-w-0">
            <div className="font-semibold leading-6">{requirement.requirement_title}</div>
            <div className="mt-1 text-sm text-muted-foreground">{requirement.recommendation}</div>
          </div>
        </div>
        <div className="grid gap-2 sm:grid-cols-3 lg:min-w-[360px]">
          <Badge variant={statusVariant(requirement.status)}>{statusLabel(requirement.status)}</Badge>
          <div className="text-sm text-muted-foreground">{percent(requirement.completion_score)}%</div>
          <div className="text-sm text-muted-foreground">{requirement.found_evidence.length} evidence</div>
        </div>
      </button>

      {expanded ? (
        <div className="space-y-4 border-t p-3">
          <div className="grid gap-2 text-sm">
            <div className="font-medium">Missing evidence</div>
            {requirement.missing_evidence.length ? (
              <div className="flex flex-wrap gap-2">
                {requirement.missing_evidence.map((item) => (
                  <Badge key={item} variant="outline">{item}</Badge>
                ))}
              </div>
            ) : (
              <div className="text-muted-foreground">No missing evidence under the current readiness rule.</div>
            )}
          </div>

          <div className="grid gap-2 text-sm">
            <div className="font-medium">Evidence found</div>
            {requirement.found_evidence.length ? (
              <div className="space-y-2">
                {requirement.found_evidence.map((mapping) => (
                  <div key={`${mapping.source_file_id}-${mapping.evidence_type}`} className="rounded-md border bg-muted/30 p-3">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <div className="break-words font-medium">{mapping.source_file_name}</div>
                        <div className="mt-1 text-muted-foreground">{mapping.evidence_type}</div>
                      </div>
                      <Badge variant={mapping.status === "accepted" ? "default" : "secondary"}>
                        {Math.round(mapping.confidence_score * 100)}%
                      </Badge>
                    </div>
                    <div className="mt-2 line-clamp-3 text-muted-foreground">{mapping.extracted_summary}</div>
                    <Button
                      className="mt-3"
                      variant="outline"
                      size="sm"
                      disabled={!filePathById.get(mapping.source_file_id)}
                      onClick={() => {
                        const path = filePathById.get(mapping.source_file_id);
                        if (path) {
                          onRevealPath(path);
                        }
                      }}
                    >
                      <FileCheck2 className="h-4 w-4" />
                      Show mapped file
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-muted-foreground">Not enough evidence yet.</div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function MappedFile({ mapping }: { mapping: PsarEvidenceMapping }) {
  return (
    <div className="rounded-lg border bg-muted/30 p-3 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="break-words font-semibold">{mapping.source_file_name}</div>
          <div className="mt-1 text-muted-foreground">{mapping.evidence_type}</div>
        </div>
        <Badge variant={mapping.status === "accepted" ? "default" : "secondary"}>
          {Math.round(mapping.confidence_score * 100)}%
        </Badge>
      </div>
    </div>
  );
}
