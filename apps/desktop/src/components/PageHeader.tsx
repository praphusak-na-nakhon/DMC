import type { ReactNode } from "react";
import { ArrowLeft } from "lucide-react";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";

type PageHeaderProps = {
  title: string;
  description: string;
  badge: string;
  icon: ReactNode;
  onBackHome?: () => void;
  backLabel?: string;
  actions?: ReactNode;
  status?: ReactNode;
};

export function PageHeader({
  title,
  description,
  badge,
  icon,
  onBackHome,
  backLabel = "กลับหน้าหลัก",
  actions,
  status,
}: PageHeaderProps) {
  return (
    <header className="border-b pb-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          {onBackHome ? (
            <Button type="button" variant="outline" size="sm" onClick={onBackHome}>
              <ArrowLeft className="h-4 w-4" />
              {backLabel}
            </Button>
          ) : null}
          <div className="mt-4 flex min-w-0 items-start gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border bg-background">
              {icon}
            </div>
            <div className="min-w-0">
              <Badge variant="default">{badge}</Badge>
              <h1 className="mt-2 break-words text-2xl font-bold leading-tight tracking-normal sm:text-3xl">
                {title}
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground sm:text-base">
                {description}
              </p>
              {status ? <div className="mt-3 flex flex-wrap gap-2">{status}</div> : null}
            </div>
          </div>
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap gap-2 lg:justify-end">{actions}</div> : null}
      </div>
    </header>
  );
}
