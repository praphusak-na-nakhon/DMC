import {
  AlertCircle,
  ArrowRight,
  BadgePercent,
  ChevronRight,
  Link2,
  LogIn,
  LogOut,
  RefreshCw,
  UserCircle2,
  WalletCards,
} from "lucide-react";
import messages from "../i18n/th.json";
import { describeAccountCode } from "../lib/errorMessages";
import { moduleDefinitions, type ModuleId } from "../lib/moduleCatalog";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Alert, AlertDescription } from "./ui/alert";
import { AiSettingsCard } from "./AiSettingsCard";
import type { AccountStatus } from "../types/contracts";

type ModuleHomeProps = {
  onOpenModule: (moduleId: ModuleId) => void;
  connectionState: "idle" | "connecting" | "ready" | "error";
  accountStatus: AccountStatus | null;
  errorMessage: string | null;
  onOpenSignIn: () => void;
  onOpenTopup: () => void;
  onSignOut: () => void;
  onRetryRuntime: () => void;
};

type ModuleActionCopy = Record<ModuleId, string>;

function creditBadgeLabel(module: (typeof moduleDefinitions)[number]) {
  if (!module.requiresCredits) {
    return messages.app.home.freeModule;
  }
  if (module.id === "formConverter") {
    return `${messages.app.home.creditModule} ${module.creditPerUnit} เครดิต/หน้า OCR`;
  }
  return `${messages.app.home.creditModule} ${module.creditPerUnit} เครดิต/รายการ`;
}

function HomeErrorBanner({
  message,
  onRetry,
  isRetrying,
}: {
  message: string;
  onRetry: () => void;
  isRetrying: boolean;
}) {
  const home = messages.app.home;

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-red-200 bg-red-50/90 p-4 text-red-700 shadow-sm sm:flex-row sm:items-center">
      <div className="flex min-w-0 flex-1 items-start gap-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-red-500 text-white shadow-sm">
          <AlertCircle className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <div className="text-base font-bold">{home.taskFailedTitle}</div>
          <div className="mt-1 break-words text-sm leading-6">{message}</div>
        </div>
      </div>
      <Button
        variant="outline"
        className="shrink-0 border-red-300 bg-white text-red-600 hover:bg-red-50 hover:text-red-700"
        onClick={onRetry}
        disabled={isRetrying}
      >
        <RefreshCw className={`h-4 w-4 ${isRetrying ? "animate-spin" : ""}`} />
        {home.retryConnection}
      </Button>
    </div>
  );
}

export function ModuleHome({
  onOpenModule,
  connectionState,
  accountStatus,
  errorMessage,
  onOpenSignIn,
  onOpenTopup,
  onSignOut,
  onRetryRuntime,
}: ModuleHomeProps) {
  const home = messages.app.home;
  const account = messages.app.account;
  const moduleActions = home.moduleActions as ModuleActionCopy;
  const wallet = accountStatus?.wallet ?? null;
  const isSignedIn = Boolean(accountStatus?.signed_in);
  const accountName = isSignedIn
    ? accountStatus?.email ?? accountStatus?.display_name ?? accountStatus?.user_id ?? account.signedIn
    : account.signInRequired;
  const accountWarningCode =
    accountStatus?.last_error ??
    (accountStatus?.signed_in && accountStatus.needs_attention ? accountStatus.message : null);
  const accountWarning = describeAccountCode(accountWarningCode) ?? accountWarningCode ?? null;

  return (
    <div className="space-y-6 text-slate-950">
      <header className="min-w-0 pb-2">
        <Badge variant="secondary" className="mb-4 rounded-md px-3 py-1 uppercase tracking-normal text-blue-950">
          {home.badge}
        </Badge>
        <h1 className="text-4xl font-bold tracking-normal text-blue-950 sm:text-5xl">
          {home.title}
        </h1>
        <p className="mt-3 max-w-4xl text-base leading-7 text-blue-950/70">
          {home.description}
        </p>
      </header>

      <Card className="border-blue-100 bg-white/95 shadow-sm">
        <CardContent className="flex flex-col gap-4 p-4 lg:flex-row lg:items-center lg:justify-between lg:p-5">
          <div className="flex min-w-0 flex-1 items-center gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-blue-950 text-white shadow-sm">
              <UserCircle2 className="h-8 w-8" />
            </div>
            <div className="min-w-0">
              <div className="truncate text-base font-bold text-blue-950">{accountName}</div>
              <div
                className={`mt-2 inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium ${
                  isSignedIn ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"
                }`}
              >
                <span className={`h-2.5 w-2.5 rounded-full ${isSignedIn ? "bg-emerald-500" : "bg-slate-400"}`} />
                {isSignedIn ? home.accountOnline : home.accountSignedOut}
              </div>
            </div>
          </div>

          <div className="hidden h-14 w-px bg-blue-100 lg:block" />

          <div className="flex min-w-[190px] items-center gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
              <WalletCards className="h-6 w-6" />
            </div>
            <div>
              <div className="text-sm font-semibold text-blue-950">{home.creditBalance}</div>
              <div className="text-2xl font-bold text-blue-950">{wallet?.available ?? "-"}</div>
            </div>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Button
              className="h-11 min-w-[180px] bg-blue-950 px-5 text-white hover:bg-blue-900"
              onClick={onOpenTopup}
            >
              <BadgePercent className="h-4 w-4" />
              {account.topup.expandLabel}
            </Button>
            <Button
              variant="outline"
              className="h-11 min-w-[160px] border-blue-200 bg-white text-blue-950 hover:bg-blue-50"
              onClick={onRetryRuntime}
              disabled={connectionState === "connecting"}
            >
              <Link2 className="h-4 w-4" />
              {home.retryConnection}
            </Button>
            {isSignedIn ? (
              <Button
                variant="outline"
                className="h-11 min-w-[150px] border-blue-200 bg-white text-blue-950 hover:bg-blue-50"
                onClick={onSignOut}
              >
                <LogOut className="h-4 w-4" />
                {account.signOut}
              </Button>
            ) : (
              <Button className="h-11 min-w-[150px] bg-blue-950 text-white hover:bg-blue-900" onClick={onOpenSignIn}>
                <LogIn className="h-4 w-4" />
                {account.signIn}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {accountWarning ? (
        <Alert variant="destructive" className="border-red-200 bg-red-50">
          <AlertDescription>{accountWarning}</AlertDescription>
        </Alert>
      ) : null}

      {errorMessage ? (
        <HomeErrorBanner
          message={errorMessage}
          onRetry={onRetryRuntime}
          isRetrying={connectionState === "connecting"}
        />
      ) : null}

      {connectionState === "ready" ? <AiSettingsCard connectionReady /> : null}

      <section className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        {moduleDefinitions.length === 0 ? (
          <Card className="md:col-span-2 xl:col-span-3">
            <CardHeader>
              <CardTitle>{home.emptyTitle}</CardTitle>
              <CardDescription>{home.emptyDescription}</CardDescription>
            </CardHeader>
          </Card>
        ) : null}

        {moduleDefinitions.map((module) => {
          const Icon = module.icon;
          const copy = home.modules[module.id];
          const isReady = module.status === "ready";
          return (
            <Card
              key={module.id}
              role="button"
              tabIndex={0}
              onClick={() => onOpenModule(module.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onOpenModule(module.id);
                }
              }}
              className="group flex min-h-[248px] min-w-0 cursor-pointer flex-col border-blue-100 bg-white/95 shadow-sm transition-colors hover:border-blue-300 hover:bg-blue-50/30 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-950"
            >
              <CardContent className="flex h-full flex-col p-5">
                <div className="flex items-start gap-4">
                  <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                    <Icon className="h-9 w-9" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-3">
                      <CardTitle className="min-w-0 text-xl leading-7 text-blue-950">{copy.title}</CardTitle>
                      <span className="mt-1 inline-flex shrink-0 items-center gap-2 whitespace-nowrap text-sm font-medium text-emerald-700">
                        {home.ready}
                        <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                      </span>
                    </div>
                    <Badge variant="secondary" className="mt-3 w-fit bg-blue-50 text-blue-700">
                      {creditBadgeLabel(module)}
                    </Badge>
                  </div>
                </div>

                <CardDescription className="mt-5 min-h-[3.5rem] text-base leading-7 text-blue-950/65">
                  {copy.description}
                </CardDescription>

                <Button
                  className="mt-auto h-11 w-full justify-between bg-blue-950 px-5 text-white hover:bg-blue-900"
                  variant={isReady ? "default" : "secondary"}
                  onClick={(event) => {
                    event.stopPropagation();
                    onOpenModule(module.id);
                  }}
                >
                  {isReady ? moduleActions[module.id] : home.openSkeleton}
                  {isReady ? <ArrowRight className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </section>

    </div>
  );
}
