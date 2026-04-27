import messages from "../i18n/th.json";
import { cardStyle, formatSummary } from "../lib/appUi";
import type { ValidateExcelResponse } from "../types/contracts";

type PreviewPanelProps = {
  preview: ValidateExcelResponse | null;
};

export function PreviewPanel({ preview }: PreviewPanelProps) {
  return (
    <section style={{ ...cardStyle, minWidth: 0 }}>
      <h2 style={{ marginTop: 0 }}>{messages.app.preview.title}</h2>
      {preview ? (
        <>
          <p style={{ marginTop: 0, lineHeight: 1.6 }}>
            {preview.detected_level} •{" "}
            {formatSummary(
              messages.app.preview.summaryRows,
              preview.rows_accepted,
              preview.rows_total,
            )}
          </p>
          <div style={{ marginBottom: "16px" }}>
            <strong>{messages.app.preview.warnings}</strong>
            <div style={{ marginTop: "8px", color: "rgb(71, 85, 105)" }}>
              {preview.warnings.length === 0
                ? "ไม่มี warning"
                : preview.warnings.map((warning) => (
                    <div key={`${warning.code}-${warning.row_index}`}>
                      {warning.code} • row {warning.row_index} • {warning.message_th}
                    </div>
                  ))}
            </div>
          </div>
          <strong>{messages.app.preview.tableTitle}</strong>
          <div style={{ overflowX: "auto", marginTop: "10px" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
              <thead>
                <tr style={{ textAlign: "left", backgroundColor: "rgb(241, 245, 249)" }}>
                  <th style={{ padding: "10px" }}>ลำดับ</th>
                  <th style={{ padding: "10px" }}>ห้อง</th>
                  <th style={{ padding: "10px" }}>เลขนักเรียน</th>
                  <th style={{ padding: "10px" }}>ชื่อ</th>
                  <th style={{ padding: "10px" }}>สถานะ</th>
                  <th style={{ padding: "10px" }}>รหัส</th>
                </tr>
              </thead>
              <tbody>
                {preview.preview.map((row) => (
                  <tr key={`${row.order}-${row.student_no}`}>
                    <td style={{ padding: "10px", borderTop: "1px solid rgb(226, 232, 240)" }}>
                      {row.order}
                    </td>
                    <td style={{ padding: "10px", borderTop: "1px solid rgb(226, 232, 240)" }}>
                      {row.room ?? "-"}
                    </td>
                    <td style={{ padding: "10px", borderTop: "1px solid rgb(226, 232, 240)" }}>
                      {row.student_no}
                    </td>
                    <td style={{ padding: "10px", borderTop: "1px solid rgb(226, 232, 240)" }}>
                      {row.first_name} {row.last_name}
                    </td>
                    <td style={{ padding: "10px", borderTop: "1px solid rgb(226, 232, 240)" }}>
                      {row.status_text}
                    </td>
                    <td style={{ padding: "10px", borderTop: "1px solid rgb(226, 232, 240)" }}>
                      {row.status_code}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p style={{ marginBottom: 0 }}>{messages.app.preview.empty}</p>
      )}
    </section>
  );
}
