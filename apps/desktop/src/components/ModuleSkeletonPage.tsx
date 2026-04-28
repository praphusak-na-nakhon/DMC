import { ArrowLeft, Braces, CheckCircle2, FileInput, FileOutput, RadioTower } from "lucide-react";
import messages from "../i18n/th.json";
import { getModuleDefinition, type ModuleId } from "../lib/moduleCatalog";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

type ModuleSkeletonPageProps = {
  moduleId: Exclude<ModuleId, "graduation">;
  onBackHome: () => void;
};

function ContractList({
  title,
  items,
  icon: Icon,
}: {
  title: string;
  items: string[];
  icon: typeof FileInput;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="h-4 w-4" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <Badge key={item} variant="secondary" className="font-mono text-xs">
              {item}
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export function ModuleSkeletonPage({ moduleId, onBackHome }: ModuleSkeletonPageProps) {
  const module = getModuleDefinition(moduleId);
  const copy = messages.app.home.modules[moduleId];
  const skeletonCopy = messages.app.home.skeletonPage;
  const Icon = module.icon;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 border-b pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <Button variant="outline" size="sm" onClick={onBackHome}>
            <ArrowLeft className="h-4 w-4" />
            {skeletonCopy.backHome}
          </Button>
          <div className="mt-5 flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl border bg-background">
              <Icon className="h-6 w-6 text-primary" />
            </div>
            <div className="min-w-0">
              <Badge variant="secondary">{messages.app.home.skeleton}</Badge>
              <h1 className="mt-2 text-3xl font-bold tracking-normal">{copy.title}</h1>
              <p className="mt-2 max-w-3xl text-muted-foreground">{copy.description}</p>
            </div>
          </div>
        </div>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{skeletonCopy.status}</CardTitle>
          <CardDescription>{skeletonCopy.statusText}</CardDescription>
        </CardHeader>
      </Card>

      <section className="grid gap-4 lg:grid-cols-2">
        <ContractList title={skeletonCopy.inputs} items={module.contract.inputs} icon={FileInput} />
        <ContractList title={skeletonCopy.validations} items={module.contract.validations} icon={CheckCircle2} />
        <ContractList title={skeletonCopy.outputs} items={module.contract.outputs} icon={FileOutput} />
        <ContractList title={skeletonCopy.events} items={module.contract.events} icon={RadioTower} />
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Braces className="h-5 w-5" />
            {skeletonCopy.dataContract}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="overflow-auto rounded-lg bg-muted p-4 text-xs">
            {JSON.stringify({ module: module.id, status: module.status, contract: module.contract }, null, 2)}
          </pre>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{skeletonCopy.nextStep}</CardTitle>
          <CardDescription>{skeletonCopy.nextStepText}</CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}
