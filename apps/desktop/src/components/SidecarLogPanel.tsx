import { MessageSquareText } from "lucide-react";
import messages from "../i18n/th.json";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

type SidecarLogPanelProps = {
  sidecarMessages: string[];
};

export function SidecarLogPanel({ sidecarMessages }: SidecarLogPanelProps) {
  return (
    <Card className="min-w-0">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>{messages.app.sidecarLog.title}</CardTitle>
            <CardDescription>ข้อความล่าสุดจาก automation runtime</CardDescription>
          </div>
          <MessageSquareText className="h-5 w-5 shrink-0 text-primary" />
        </div>
      </CardHeader>
      <CardContent>
        {sidecarMessages.length > 0 ? (
          <div className="panel-scroll grid max-h-[360px] gap-2 overflow-auto pr-1">
            {sidecarMessages.map((message, index) => (
              <div
                key={`${message}-${index}`}
                className="min-w-0 break-words rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
              >
                {message}
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed bg-muted/30 p-5 text-center text-sm text-muted-foreground">
            {messages.app.sidecarLog.empty}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
