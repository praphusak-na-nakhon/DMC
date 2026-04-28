import { AlertTriangle, CheckCircle2, FileSpreadsheet } from "lucide-react";
import messages from "../i18n/th.json";
import { formatSummary } from "../lib/appUi";
import { Badge } from "./ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import type { ValidateExcelResponse } from "../types/contracts";

type PreviewPanelProps = {
  preview: ValidateExcelResponse | null;
};

export function PreviewPanel({ preview }: PreviewPanelProps) {
  return (
    <Card className="min-w-0">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>{messages.app.preview.title}</CardTitle>
            <CardDescription>ตรวจไฟล์ก่อนเริ่มงานจริงทุกครั้ง</CardDescription>
          </div>
          <FileSpreadsheet className="h-5 w-5 shrink-0 text-primary" />
        </div>
      </CardHeader>
      <CardContent className="min-w-0">
        {preview ? (
          <div className="space-y-4">
            <div className="grid gap-2 sm:grid-cols-3">
              <div className="rounded-lg border bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground">ระดับชั้น</div>
                <div className="mt-1 text-lg font-semibold">{preview.detected_level}</div>
              </div>
              <div className="rounded-lg border bg-muted/40 p-3">
                <div className="text-xs">รับข้อมูล</div>
                <div className="mt-1 text-lg font-semibold">{preview.rows_accepted}</div>
              </div>
              <div className="rounded-lg border bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground">แถวทั้งหมด</div>
                <div className="mt-1 text-lg font-semibold">{preview.rows_total}</div>
              </div>
            </div>

            <p className="text-sm leading-6 text-muted-foreground">
              {formatSummary(messages.app.preview.summaryRows, preview.rows_accepted, preview.rows_total)}
            </p>

            <div className="rounded-lg border p-3">
              <div className="mb-2 flex items-center gap-2 font-semibold">
                {preview.warnings.length === 0 ? (
                  <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <AlertTriangle className="h-4 w-4 text-destructive" />
                )}
                {messages.app.preview.warnings}
                <Badge
                  variant="outline"
                  className={
                    preview.warnings.length === 0
                      ? "border-border bg-secondary text-secondary-foreground"
                      : "border-destructive/30 bg-destructive/15 text-destructive"
                  }
                >
                  {preview.warnings.length === 0 ? "ไม่มี warning" : `${preview.warnings.length} รายการ`}
                </Badge>
              </div>
              <div className="grid gap-1 text-sm text-muted-foreground">
                {preview.warnings.length === 0
                  ? "ไม่มี warning"
                  : preview.warnings.map((warning) => (
                      <div key={`${warning.code}-${warning.row_index}`} className="break-words">
                        {warning.code} - row {warning.row_index} - {warning.message_th}
                      </div>
                    ))}
              </div>
            </div>

            <div>
              <div className="mb-2 font-semibold">{messages.app.preview.tableTitle}</div>
              <div className="panel-scroll max-h-[520px] overflow-auto rounded-lg border">
                <table className="w-full min-w-[760px] border-collapse text-sm">
                  <thead className="sticky top-0 bg-muted text-left">
                    <tr>
                      <th className="px-3 py-2 font-semibold">ลำดับ</th>
                      <th className="px-3 py-2 font-semibold">ห้อง</th>
                      <th className="px-3 py-2 font-semibold">เลขนักเรียน</th>
                      <th className="px-3 py-2 font-semibold">ชื่อ</th>
                      <th className="px-3 py-2 font-semibold">สถานะ</th>
                      <th className="px-3 py-2 font-semibold">รหัส</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.preview.map((row) => (
                      <tr key={`${row.order}-${row.student_no}`} className="border-t">
                        <td className="px-3 py-2">{row.order}</td>
                        <td className="px-3 py-2">{row.room ?? "-"}</td>
                        <td className="px-3 py-2 font-medium">{row.student_no}</td>
                        <td className="px-3 py-2">
                          {row.first_name} {row.last_name}
                        </td>
                        <td className="px-3 py-2 text-muted-foreground">{row.status_text}</td>
                        <td className="px-3 py-2">
                          <Badge variant="outline">{row.status_code}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed bg-muted/30 p-6 text-center text-sm text-muted-foreground">
            {messages.app.preview.empty}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
