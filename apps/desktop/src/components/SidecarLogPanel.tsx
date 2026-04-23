import messages from "../i18n/th.json";
import { cardStyle } from "../lib/appUi";

type SidecarLogPanelProps = {
  sidecarMessages: string[];
};

export function SidecarLogPanel({ sidecarMessages }: SidecarLogPanelProps) {
  return (
    <section style={cardStyle}>
      <h2 style={{ marginTop: 0 }}>{messages.app.sidecarLog.title}</h2>
      {sidecarMessages.length > 0 ? (
        <div style={{ display: "grid", gap: "8px" }}>
          {sidecarMessages.map((message, index) => (
            <div
              key={`${message}-${index}`}
              style={{
                borderRadius: "12px",
                backgroundColor: "rgb(248, 250, 252)",
                padding: "10px 12px",
                color: "rgb(51, 65, 85)",
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
