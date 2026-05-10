import { ArrowLeft, CheckCircle2, WalletCards } from "lucide-react";
import { useState } from "react";
import messages from "../i18n/th.json";
import type { AccountStatus } from "../types/contracts";
import { Alert, AlertDescription } from "./ui/alert";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

type CreditTopupPageProps = {
  accountStatus: AccountStatus | null;
  onBackHome: () => void;
  onOpenSignIn: () => void;
};

export function CreditTopupPage({ accountStatus, onBackHome, onOpenSignIn }: CreditTopupPageProps) {
  const account = messages.app.account;
  const [selectedTopupPackageId, setSelectedTopupPackageId] = useState<string | null>(null);
  const selectedTopupPackage =
    account.topup.packages.find((packageOption) => packageOption.id === selectedTopupPackageId) ?? null;

  function chooseTopupPackage(packageId: string) {
    if (!accountStatus?.signed_in) {
      onOpenSignIn();
      return;
    }
    setSelectedTopupPackageId(packageId);
  }

  return (
    <div className="space-y-4 text-blue-950">
      <Button variant="outline" className="border-blue-200 bg-white hover:bg-blue-50" onClick={onBackHome}>
        <ArrowLeft className="h-4 w-4" />
        {messages.app.home.skeletonPage.backHome}
      </Button>

      <Card className="border-blue-100 bg-white/95 shadow-sm">
        <CardHeader className="pb-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle className="text-xl text-blue-950">{account.topup.title}</CardTitle>
              <CardDescription className="mt-2 leading-6 text-blue-950/65">
                {account.topup.description}
              </CardDescription>
            </div>
            <Badge variant="outline" className="w-fit border-blue-100 bg-blue-50 px-3 py-1 text-blue-950">
              {account.topup.paymentMode}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 p-5 pt-0 md:grid-cols-3">
          {account.topup.packages.map((packageOption, index) => {
            const isSelected = packageOption.id === selectedTopupPackageId;
            return (
              <div
                key={packageOption.id}
                className={`flex min-w-0 flex-col rounded-lg border bg-white p-4 transition-colors ${
                  isSelected ? "border-blue-700 bg-blue-50/60" : "border-blue-100"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 text-lg font-bold text-blue-950">{packageOption.name}</div>
                  <Badge
                    variant={index === 0 ? "secondary" : "default"}
                    className={index === 0 ? "shrink-0 bg-slate-100 text-blue-950" : "shrink-0 bg-blue-950 text-white"}
                  >
                    {packageOption.badge}
                  </Badge>
                </div>

                <div className="mt-6 flex items-end gap-3">
                  <span className="text-4xl font-bold leading-none text-blue-950">{packageOption.credits}</span>
                  <span className="pb-1 text-base text-blue-950/55">{account.topup.creditsUnit}</span>
                </div>

                <div className="mt-4 text-base text-blue-950/55">
                  <span className="text-xl font-bold text-blue-950">{packageOption.price}</span>{" "}
                  {account.topup.bahtUnit}
                </div>

                <div className="mt-5 rounded-md bg-slate-100 px-3 py-3 text-sm font-medium text-blue-950">
                  {packageOption.unitRate}
                </div>

                <p className="mt-4 min-h-[3rem] text-sm leading-6 text-blue-950/65">{packageOption.description}</p>

                <Button
                  className="mt-auto h-11 w-full"
                  variant={isSelected ? "secondary" : index === 0 ? "outline" : "default"}
                  onClick={() => chooseTopupPackage(packageOption.id)}
                  aria-label={`${account.topup.cta} ${packageOption.name}`}
                >
                  {isSelected ? <CheckCircle2 className="h-4 w-4" /> : <WalletCards className="h-4 w-4" />}
                  {isSelected ? account.topup.selectedCta : account.topup.cta}
                </Button>
              </div>
            );
          })}
        </CardContent>
      </Card>

      {selectedTopupPackage ? (
        <Alert className="border-blue-100 bg-blue-50 text-blue-950">
          <AlertDescription>
            {account.topup.selectedMessage.replace("{name}", selectedTopupPackage.name)}
          </AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}
