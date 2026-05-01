import { ArrowLeft, Bot, CheckCircle2, FileOutput, FileText, Loader2, Search, UploadCloud } from "lucide-react";
import { useMemo, useState } from "react";
import messages from "../i18n/th.json";
import { buildJobId } from "../lib/appUi";
import {
  exportConvertedExcel,
  getConversionStatus,
  openPdfDialog,
  saveReviewEdits,
  startFormConversion,
  validateFormPdf,
} from "../lib/rpcClient";
import type {
  AccountStatus,
  FormConversionRecord,
  FormConversionStatusResponse,
  ValidateFormPdfResponse,
} from "../types/contracts";
import { Alert, AlertDescription } from "./ui/alert";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Progress } from "./ui/progress";

type FormConverterPageProps = {
  accountStatus: AccountStatus | null;
  onBackHome: () => void;
  onRefreshWallet: () => void;
  onRevealPath: (path: string) => void;
};

function statusVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  if (status === "ready" || status === "done" || status === "reviewed") {
    return "default";
  }
  if (status === "invalid" || status === "failed") {
    return "destructive";
  }
  if (status === "needs_review") {
    return "secondary";
  }
  return "outline";
}

export function FormConverterPage({
  accountStatus,
  onBackHome,
  onRefreshWallet,
  onRevealPath,
}: FormConverterPageProps) {
  const copy = messages.app.formConverter;
  const accountCopy = messages.app.account;
  const [pdfPath, setPdfPath] = useState("");
  const [schoolYear, setSchoolYear] = useState("");
  const [consent, setConsent] = useState(false);
  const [validation, setValidation] = useState<ValidateFormPdfResponse | null>(null);
  const [conversion, setConversion] = useState<FormConversionStatusResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [isSavingReview, setIsSavingReview] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  const availableCredits = accountStatus?.wallet?.available ?? 0;
  const creditEstimate = validation?.credit_estimate ?? 0;
  const accountErrors = accountCopy.errors as Record<string, string>;
  const formErrors = copy.errors as Record<string, string>;
  const blocksStart =
    !validation ||
    !validation.supported_template ||
    !accountStatus?.signed_in ||
    availableCredits < creditEstimate ||
    !consent;
  const progressPercent = useMemo(() => {
    if (!conversion?.total) {
      return 0;
    }
    return Math.round((conversion.processed / conversion.total) * 100);
  }, [conversion]);

  async function handleBrowsePdf() {
    const selected = await openPdfDialog();
    if (selected) {
      setPdfPath(selected);
      setValidation(null);
      setConversion(null);
      setErrorMessage(null);
    }
  }

  async function handleValidatePdf() {
    if (!pdfPath.trim()) {
      setErrorMessage(copy.errors.selectPdf);
      return;
    }
    setIsValidating(true);
    setErrorMessage(null);
    try {
      const result = await validateFormPdf(pdfPath.trim());
      setValidation(result);
    } catch (error) {
      setErrorMessage(readableError(error));
    } finally {
      setIsValidating(false);
    }
  }

  async function handleStartConversion() {
    if (blocksStart || !validation) {
      setErrorMessage(startBlockReason());
      return;
    }
    const confirmed =
      typeof window === "undefined" ||
      window.confirm(
        [
          copy.confirmTitle,
          "",
          `${copy.fileLabel}: ${validation.file_name}`,
          `${copy.recordEstimate}: ${validation.estimated_records}`,
          `${copy.creditEstimate}: ${validation.credit_estimate}`,
          "",
          copy.cloudConsent,
        ].join("\n"),
      );
    if (!confirmed) {
      return;
    }
    setIsStarting(true);
    setErrorMessage(null);
    try {
      const response = await startFormConversion({
        jobId: buildJobId(),
        pdfPath: validation.path,
        templateType: validation.template_type,
        schoolYear: schoolYear.trim() || null,
        confirmedAiProcessing: consent,
      });
      const status = await getConversionStatus(response.job_id);
      setConversion(status);
      onRefreshWallet();
    } catch (error) {
      setErrorMessage(readableError(error));
    } finally {
      setIsStarting(false);
    }
  }

  async function handleSaveReview() {
    if (!conversion) {
      return;
    }
    setIsSavingReview(true);
    setErrorMessage(null);
    try {
      const status = await saveReviewEdits(conversion.job_id, conversion.records);
      setConversion(status);
    } catch (error) {
      setErrorMessage(readableError(error));
    } finally {
      setIsSavingReview(false);
    }
  }

  async function handleExportExcel() {
    if (!conversion) {
      return;
    }
    setIsExporting(true);
    setErrorMessage(null);
    try {
      const result = await exportConvertedExcel(conversion.job_id);
      const status = await getConversionStatus(result.job_id);
      setConversion(status);
      onRefreshWallet();
    } catch (error) {
      setErrorMessage(readableError(error));
    } finally {
      setIsExporting(false);
    }
  }

  function readableError(error: unknown): string {
    const raw = error instanceof Error ? error.message : String(error);
    const code = raw.match(/[A-Z][A-Z0-9_]+/)?.[0] ?? raw;
    return formErrors[code] ?? accountErrors[code] ?? raw;
  }

  function startBlockReason(): string {
    if (!accountStatus?.signed_in) {
      return accountCopy.signInBeforeLive;
    }
    if (validation && availableCredits < validation.credit_estimate) {
      return accountCopy.insufficientCredits;
    }
    if (!consent) {
      return copy.errors.consentRequired;
    }
    return copy.errors.validateFirst;
  }

  function updateField(recordId: string, fieldName: string, value: string) {
    setConversion((current) => {
      if (!current) {
        return current;
      }
      const records = current.records.map((record) => {
        if (record.record_id !== recordId) {
          return record;
        }
        const fields = record.fields.map((field) =>
          field.field_name === fieldName ? { ...field, value, edited: true } : field,
        );
        return { ...record, fields } satisfies FormConversionRecord;
      });
      return { ...current, records };
    });
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 border-b pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <Button variant="outline" size="sm" onClick={onBackHome}>
            <ArrowLeft className="h-4 w-4" />
            {copy.backHome}
          </Button>
          <div className="mt-5 flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl border bg-background">
              <FileText className="h-6 w-6 text-primary" />
            </div>
            <div>
              <Badge variant="default">{copy.readyBadge}</Badge>
              <h1 className="mt-2 text-3xl font-bold tracking-normal">{copy.title}</h1>
              <p className="mt-2 max-w-3xl text-muted-foreground">{copy.description}</p>
            </div>
          </div>
        </div>
      </header>

      {errorMessage ? (
        <Alert variant="destructive">
          <AlertDescription>{errorMessage}</AlertDescription>
        </Alert>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader>
            <CardTitle>{copy.steps.uploadTitle}</CardTitle>
            <CardDescription>{copy.steps.uploadDescription}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-2">
              <Label>{copy.pdfPath}</Label>
              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                <Input value={pdfPath} onChange={(event) => setPdfPath(event.target.value)} placeholder={copy.pdfPlaceholder} />
                <Button variant="outline" onClick={() => void handleBrowsePdf()}>
                  <FileText className="h-4 w-4" />
                  {copy.browsePdf}
                </Button>
              </div>
            </div>
            <div className="grid gap-2">
              <Label>{copy.schoolYear}</Label>
              <Input value={schoolYear} onChange={(event) => setSchoolYear(event.target.value)} placeholder="2569" />
            </div>
            <label className="flex gap-3 rounded-lg border bg-muted/30 p-3 text-sm leading-6">
              <input
                className="mt-1 h-4 w-4"
                type="checkbox"
                checked={consent}
                onChange={(event) => setConsent(event.target.checked)}
              />
              <span>{copy.cloudConsent}</span>
            </label>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" disabled={isValidating} onClick={() => void handleValidatePdf()}>
                {isValidating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                {copy.validatePdf}
              </Button>
              <Button disabled={blocksStart || isStarting} onClick={() => void handleStartConversion()}>
                {isStarting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
                {copy.startAiRead}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{copy.preflightTitle}</CardTitle>
            <CardDescription>{copy.preflightDescription}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between gap-3">
              <span className="text-muted-foreground">{copy.pageCount}</span>
              <strong>{validation?.page_count ?? "-"}</strong>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-muted-foreground">{copy.recordEstimate}</span>
              <strong>{validation?.estimated_records ?? "-"}</strong>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-muted-foreground">{copy.creditEstimate}</span>
              <strong>{validation?.credit_estimate ?? "-"}</strong>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-muted-foreground">{accountCopy.availableCredits}</span>
              <strong>{availableCredits}</strong>
            </div>
            {validation?.warnings.map((warning) => (
              <Alert key={warning.code}>
                <AlertDescription>{warning.message_th}</AlertDescription>
              </Alert>
            ))}
          </CardContent>
        </Card>
      </section>

      {conversion ? (
        <>
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <CardTitle>{copy.reviewTitle}</CardTitle>
                  <CardDescription>{copy.reviewDescription}</CardDescription>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {conversion.ocr_provider ? <Badge variant="outline">{`${copy.provider}: ${conversion.ocr_provider}`}</Badge> : null}
                  <Badge variant={statusVariant(conversion.status)}>{conversion.status}</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <Progress value={progressPercent} />
              <div className="grid gap-3 sm:grid-cols-4">
                <Metric label={copy.summary.total} value={conversion.summary.records_total} />
                <Metric label={copy.summary.ready} value={conversion.summary.ready_records} />
                <Metric label={copy.summary.needsReview} value={conversion.summary.needs_review_records} />
                <Metric label={copy.summary.invalid} value={conversion.summary.invalid_records} />
              </div>
              <div className="space-y-4">
                {conversion.records.map((record) => (
                  <div key={record.record_id} className="rounded-lg border p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div className="font-semibold">{copy.pageLabel.replace("{page}", String(record.page_number))}</div>
                      <Badge variant={statusVariant(record.status)}>{record.status}</Badge>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                      {record.fields.map((field) => (
                        <div key={`${record.record_id}-${field.field_name}`} className="grid gap-2">
                          <div className="flex items-center justify-between gap-2">
                            <Label>{field.label_th}</Label>
                            <Badge variant={statusVariant(field.status)}>
                              {Math.round(field.confidence * 100)}%
                            </Badge>
                          </div>
                          <Input
                            value={field.value}
                            onChange={(event) => updateField(record.record_id, field.field_name, event.target.value)}
                          />
                          {field.alternatives.length ? (
                            <div className="flex flex-wrap gap-2">
                              {field.alternatives.slice(0, 4).map((alternative) => (
                                <Button
                                  key={`${field.field_name}-${alternative}`}
                                  type="button"
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => updateField(record.record_id, field.field_name, alternative)}
                                >
                                  {alternative}
                                </Button>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" disabled={isSavingReview} onClick={() => void handleSaveReview()}>
                  {isSavingReview ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                  {copy.saveReview}
                </Button>
                <Button disabled={conversion.status !== "reviewed" || isExporting} onClick={() => void handleExportExcel()}>
                  {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileOutput className="h-4 w-4" />}
                  {copy.exportExcel}
                </Button>
              </div>
            </CardContent>
          </Card>

          {conversion.status === "done" ? (
            <Card>
              <CardHeader>
                <CardTitle>{copy.outputTitle}</CardTitle>
                <CardDescription>{copy.outputDescription}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {conversion.excel_path ? (
                  <Button variant="outline" onClick={() => onRevealPath(conversion.excel_path ?? "")}>
                    <FileOutput className="h-4 w-4" />
                    {copy.openExcel}
                  </Button>
                ) : null}
                {conversion.report_path ? (
                  <Button variant="outline" onClick={() => onRevealPath(conversion.report_path ?? "")}>
                    <UploadCloud className="h-4 w-4" />
                    {copy.openReport}
                  </Button>
                ) : null}
              </CardContent>
            </Card>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border bg-muted/40 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-bold">{value}</div>
    </div>
  );
}
