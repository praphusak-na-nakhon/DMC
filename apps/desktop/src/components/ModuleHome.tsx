import { Loader2, LogIn, LogOut, RefreshCw, UploadCloud, WalletCards } from "lucide-react";
import messages from "../i18n/th.json";
import { formatTimestamp } from "../lib/appUi";
import { moduleDefinitions, type ModuleId } from "../lib/moduleCatalog";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { SupportToolsPanel } from "./SupportToolsPanel";
import type { AccountStatus, AvailableUpdate, DatabaseStatus, UpdaterStatus } from "../types/contracts";

type ModuleHomeProps = {
  onOpenModule: (moduleId: ModuleId) => void;
  updaterStatus: UpdaterStatus | null;
  availableUpdate: AvailableUpdate | null;
  updateMessage: string | null;
  updateProgress: { downloaded: number; contentLength: number | null } | null;
  isCheckingUpdate: boolean;
  isInstallingUpdate: boolean;
  connectionState: "idle" | "connecting" | "ready" | "error";
  databaseStatus: DatabaseStatus | null;
  accountStatus: AccountStatus | null;
  accountEmail: string;
  accountPassword: string;
  isSigningIn: boolean;
  isCreatingBackup: boolean;
  isRestoringBackup: boolean;
  isExportingDiagnostics: boolean;
  onAccountEmailChange: (value: string) => void;
  onAccountPasswordChange: (value: string) => void;
  onSignIn: () => void;
  onSignOut: () => void;
  onRefreshWallet: () => void;
  onCheckForUpdates: () => void;
  onInstallUpdate: () => void;
  onRefreshDatabaseStatus: () => void;
  onCreateBackup: () => void;
  onRestoreBackup: () => void;
  onExportDiagnostics: () => void;
};

export function ModuleHome({
  onOpenModule,
  updaterStatus,
  availableUpdate,
  updateMessage,
  updateProgress,
  isCheckingUpdate,
  isInstallingUpdate,
  connectionState,
  databaseStatus,
  accountStatus,
  accountEmail,
  accountPassword,
  isSigningIn,
  isCreatingBackup,
  isRestoringBackup,
  isExportingDiagnostics,
  onAccountEmailChange,
  onAccountPasswordChange,
  onSignIn,
  onSignOut,
  onRefreshWallet,
  onCheckForUpdates,
  onInstallUpdate,
  onRefreshDatabaseStatus,
  onCreateBackup,
  onRestoreBackup,
  onExportDiagnostics,
}: ModuleHomeProps) {
  const home = messages.app.home;
  const account = messages.app.account;
  const wallet = accountStatus?.wallet ?? null;

  return (
    <div className="space-y-6">
      <header className="flex min-w-0 flex-col gap-4 border-b pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <Badge variant="secondary" className="mb-3 uppercase tracking-normal">
            {home.badge}
          </Badge>
          <h1 className="text-3xl font-bold tracking-normal text-foreground sm:text-4xl">
            {home.title}
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base">
            {home.description}
          </p>
        </div>
      </header>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <CardTitle>{account.title}</CardTitle>
              <CardDescription>
                {account.description}
              </CardDescription>
            </div>
            <Badge variant={accountStatus?.signed_in ? "default" : "secondary"}>
              {accountStatus?.signed_in ? account.signedIn : account.signInRequired}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.65fr)]">
          {accountStatus?.signed_in ? (
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg border bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground">{account.user}</div>
                <div className="mt-1 break-words font-semibold">{accountStatus.email ?? accountStatus.user_id}</div>
              </div>
              <div className="rounded-lg border bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground">{account.availableCredits}</div>
                <div className="mt-1 text-2xl font-bold">{wallet?.available ?? "-"}</div>
              </div>
              <div className="rounded-lg border bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground">{account.reservedTotal}</div>
                <div className="mt-1 font-semibold">
                  {wallet ? `${wallet.reserved} / ${wallet.balance}` : "-"}
                </div>
              </div>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              <input
                className="h-10 rounded-md border bg-background px-3 text-sm"
                type="email"
                value={accountEmail}
                onChange={(event) => onAccountEmailChange(event.target.value)}
                placeholder={account.emailPlaceholder}
              />
              <input
                className="h-10 rounded-md border bg-background px-3 text-sm"
                type="password"
                value={accountPassword}
                onChange={(event) => onAccountPasswordChange(event.target.value)}
                placeholder={account.passwordPlaceholder}
              />
            </div>
          )}

          <div className="flex flex-wrap items-start gap-2 lg:justify-end">
            {accountStatus?.signed_in ? (
              <>
                <Button variant="outline" onClick={onRefreshWallet}>
                  <WalletCards className="h-4 w-4" />
                  {account.refreshCredits}
                </Button>
                <Button variant="secondary" onClick={onSignOut}>
                  <LogOut className="h-4 w-4" />
                  {account.signOut}
                </Button>
              </>
            ) : (
              <Button disabled={isSigningIn} onClick={onSignIn}>
                {isSigningIn ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
                {account.signIn}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <section className="grid gap-4 lg:grid-cols-3">
        {moduleDefinitions.length === 0 ? (
          <Card className="lg:col-span-3">
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
              className="flex min-h-[260px] min-w-0 flex-col transition-colors hover:border-primary/40 hover:bg-muted/30"
            >
              <CardHeader>
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg border bg-background">
                    <Icon className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <Badge variant={isReady ? "default" : "secondary"}>
                    {isReady ? home.ready : home.skeleton}
                  </Badge>
                </div>
                {module.requiresCredits ? (
                  <Badge variant="outline" className="mb-3 w-fit">
                    {account.creditBadge.replace("{credits}", String(module.creditPerUnit))}
                  </Badge>
                ) : null}
                <CardTitle className="leading-7">{copy.title}</CardTitle>
                <CardDescription className="leading-6">{copy.description}</CardDescription>
              </CardHeader>
              <CardContent className="mt-auto">
                <Button className="w-full" variant={isReady ? "default" : "secondary"} onClick={() => onOpenModule(module.id)}>
                  {isReady ? home.openModule : home.openSkeleton}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <CardTitle>{home.updatesTitle}</CardTitle>
                <CardDescription>{home.updatesDescription}</CardDescription>
              </div>
              <Badge variant={updaterStatus?.configured ? "default" : "secondary"}>
                {updaterStatus?.configured ? home.updatesReady : home.updatesNotConfigured}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid gap-3 lg:grid-cols-3">
              <div className="rounded-lg border bg-muted/40 p-3">
                <div className="text-xs text-muted-foreground">{home.currentVersion}</div>
                <div className="mt-1 font-semibold">{updaterStatus?.current_version ?? "-"}</div>
              </div>
              <div className="rounded-lg border bg-muted/40 p-3 lg:col-span-2">
                <div className="text-xs text-muted-foreground">{home.endpoint}</div>
                <div className="mt-1 break-words text-sm font-medium">{updaterStatus?.endpoint ?? "-"}</div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button variant="outline" disabled={isCheckingUpdate} onClick={onCheckForUpdates}>
                {isCheckingUpdate ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                {home.checkUpdates}
              </Button>
              <Button disabled={!availableUpdate || isInstallingUpdate} onClick={onInstallUpdate}>
                {isInstallingUpdate ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                {home.installUpdate}
              </Button>
            </div>

            {availableUpdate ? (
              <div className="grid gap-1 rounded-lg border bg-muted/40 p-3 text-sm text-muted-foreground">
                <div className="font-medium text-foreground">{home.updateAvailable}: {availableUpdate.version}</div>
                <div>{home.publishedAt}: {formatTimestamp(availableUpdate.date)}</div>
                <div className="break-words">{home.updateDetails}: {availableUpdate.body ?? "-"}</div>
              </div>
            ) : null}

            {updateProgress ? (
              <div className="text-sm text-muted-foreground">
                {home.downloadProgress} {updateProgress.downloaded}
                {updateProgress.contentLength ? ` / ${updateProgress.contentLength}` : ""} bytes
              </div>
            ) : null}

            {updateMessage ? <div className="break-words text-sm text-muted-foreground">{updateMessage}</div> : null}
          </CardContent>
        </Card>

        <SupportToolsPanel
          connectionState={connectionState}
          databaseStatus={databaseStatus}
          accountStatus={accountStatus}
          isCreatingBackup={isCreatingBackup}
          isRestoringBackup={isRestoringBackup}
          isExportingDiagnostics={isExportingDiagnostics}
          onRefreshDatabaseStatus={onRefreshDatabaseStatus}
          onCreateBackup={onCreateBackup}
          onRestoreBackup={onRestoreBackup}
          onExportDiagnostics={onExportDiagnostics}
        />
      </section>
    </div>
  );
}
