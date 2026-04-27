import messages from "../i18n/th.json";
import { cardStyle } from "../lib/appUi";

const logTextStyle = {
  minWidth: 0,
  overflowWrap: "anywhere",
  wordBreak: "break-word",
} as const;

type SidecarLogPanelProps = {
  sidecarMessages: string[];
};

export function SidecarLogPanel({ sidecarMessages }: SidecarLogPanelProps) {
  return (
    <section style={{ ...cardStyle, minWidth: 0 }}>
      <h2 style={{ marginTop: 0 }}>{messages.app.sidecarLog.title}</h2>
      {sidecarMessages.length > 0 ? (
        <div style={{ display: "grid", gap: "8px", minWidth: 0 }}>
          {sidecarMessages.map((message, index) => (
            <div
              key={`${message}-${index}`}
              style={{
                borderRadius: "12px",
                backgroundColor: "rgb(248, 250, 252)",
                padding: "10px 12px",
                color: "rgb(51, 65, 85)",
                ...logTextStyle,
              }}
            >
              {message}
            </div>
          ))}
        </div>
      ) : (
        <p style={{ marginBottom: 0 }}>{messages.app.sidecarLog.empty}</p>
      )}
    </section>
  );
}
