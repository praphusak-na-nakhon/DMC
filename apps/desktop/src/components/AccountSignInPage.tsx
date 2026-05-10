import { FileText, Loader2, LogIn, LogOut, WalletCards } from "lucide-react";
import messages from "../i18n/th.json";
import type { AccountStatus } from "../types/contracts";
import { PageHeader } from "./PageHeader";
import { SystemErrorAlert } from "./SystemErrorAlert";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";

type AccountSignInPageProps = {
  accountStatus: AccountStatus | null;
  accountEmail: string;
  accountPassword: string;
  errorMessage: string | null;
  isSigningIn: boolean;
  onBackHome: () => void;
  onAccountEmailChange: (value: string) => void;
  onAccountPasswordChange: (value: string) => void;
  onSignIn: () => void;
  onSignOut: () => void;
  onRefreshWallet: () => void;
};

export function AccountSignInPage({
  accountStatus,
  accountEmail,
  accountPassword,
  errorMessage,
  isSigningIn,
  onBackHome,
  onAccountEmailChange,
  onAccountPasswordChange,
  onSignIn,
  onSignOut,
  onRefreshWallet,
}: AccountSignInPageProps) {
  const account = messages.app.account;
  const wallet = accountStatus?.wallet ?? null;

  return (
    <div className="space-y-6">
      <PageHeader
        onBackHome={onBackHome}
        badge={account.signInRequired}
        title={account.title}
        description={account.description}
        icon={<LogIn className="h-5 w-5 text-primary" />}
      />

      {errorMessage ? <SystemErrorAlert message={errorMessage} /> : null}

      <section className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(320px,0.6fr)]">
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle>{accountStatus?.signed_in ? account.signedIn : account.signIn}</CardTitle>
                <CardDescription>
                  {accountStatus?.signed_in
                    ? "บัญชีนี้พร้อมใช้สำหรับงานที่ต้องใช้เครดิต"
                    : "กรอกอีเมลและรหัสผ่านเพื่อเชื่อมบัญชีเครดิตกับเครื่องนี้"}
                </CardDescription>
              </div>
              <Badge variant={accountStatus?.signed_in ? "default" : "secondary"}>
                {accountStatus?.signed_in ? account.signedIn : account.signInRequired}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {accountStatus?.signed_in ? (
              <div className="grid gap-4">
                <div className="rounded-lg border bg-muted/40 p-3">
                  <div className="text-xs text-muted-foreground">{account.user}</div>
                  <div className="mt-1 break-words font-semibold">
                    {accountStatus.email ?? accountStatus.user_id}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" onClick={onRefreshWallet}>
                    <WalletCards className="h-4 w-4" />
                    {account.refreshCredits}
                  </Button>
                  <Button variant="secondary" onClick={onSignOut}>
                    <LogOut className="h-4 w-4" />
                    {account.signOut}
                  </Button>
                </div>
              </div>
            ) : (
              <form
                className="grid gap-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  onSignIn();
                }}
              >
                <div className="grid gap-2">
                  <Label htmlFor="account-signin-email">{account.emailLabel}</Label>
                  <Input
                    id="account-signin-email"
                    type="email"
                    value={accountEmail}
                    onChange={(event) => onAccountEmailChange(event.target.value)}
                    placeholder={account.emailPlaceholder}
                    autoComplete="email"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="account-signin-password">{account.passwordLabel}</Label>
                  <Input
                    id="account-signin-password"
                    type="password"
                    value={accountPassword}
                    onChange={(event) => onAccountPasswordChange(event.target.value)}
                    placeholder={account.passwordPlaceholder}
                    autoComplete="current-password"
                  />
                </div>
                <Button type="submit" disabled={isSigningIn}>
                  {isSigningIn ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
                  {account.signIn}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>เครดิต</CardTitle>
            <CardDescription>ยอดเครดิตจะอัปเดตหลังลงชื่อเข้าใช้สำเร็จ</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <div className="rounded-lg border bg-muted/40 p-3">
              <div className="text-xs text-muted-foreground">{account.availableCredits}</div>
              <div className="mt-1 text-2xl font-bold">{wallet?.available ?? "-"}</div>
            </div>
            <div className="rounded-lg border bg-muted/40 p-3">
              <div className="text-xs text-muted-foreground">{account.reservedTotal}</div>
              <div className="mt-1 font-semibold">{wallet ? `${wallet.reserved} / ${wallet.balance}` : "-"}</div>
            </div>
            <div className="flex items-start gap-2 rounded-lg border bg-muted/40 p-3 text-muted-foreground">
              <FileText className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{account.reserveNotice}</span>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
