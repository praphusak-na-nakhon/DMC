import { useCallback, useEffect, useRef, useState } from "react";
import messages from "../i18n/th.json";
import { deleteAiApiKey, getAiSettings, saveAiApiKey, testAiConnection } from "../lib/rpcClient";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";
import { Label } from "./ui/label";

type AiSettingsCardProps = {
  connectionReady: boolean;
};

type Feedback = "testSuccess" | "testFailure" | "actionFailure" | null;

export function AiSettingsCard({ connectionReady }: AiSettingsCardProps) {
  const ai = messages.app.home.aiSettings;
  const [apiKey, setApiKey] = useState("");
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [settingsLoadState, setSettingsLoadState] = useState<"idle" | "loading" | "ready" | "failed">("idle");
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const settingsRequestGeneration = useRef(0);

  const loadSettings = useCallback(() => {
    const generation = settingsRequestGeneration.current + 1;
    settingsRequestGeneration.current = generation;
    setSettingsLoadState("loading");

    void getAiSettings("gemini")
      .then((settings) => {
        if (settingsRequestGeneration.current === generation) {
          setConfigured(settings.configured);
          setSettingsLoadState("ready");
        }
      })
      .catch(() => {
        if (settingsRequestGeneration.current === generation) {
          setConfigured(null);
          setSettingsLoadState("failed");
        }
      });
  }, []);

  useEffect(() => {
    if (!connectionReady) {
      settingsRequestGeneration.current += 1;
      setConfigured(null);
      setSettingsLoadState("idle");
      return;
    }

    loadSettings();

    return () => {
      settingsRequestGeneration.current += 1;
    };
  }, [connectionReady, loadSettings]);

  async function saveKey() {
    const submittedKey = apiKey.trim();
    if (!submittedKey) {
      return;
    }

    const hadPendingSettingsLoad = settingsLoadState === "loading";
    settingsRequestGeneration.current += 1;
    setIsSaving(true);
    setFeedback(null);
    try {
      const settings = await saveAiApiKey("gemini", submittedKey);
      setConfigured(settings.configured);
      setSettingsLoadState("ready");
      setApiKey("");
    } catch {
      if (hadPendingSettingsLoad) {
        setConfigured(null);
        setSettingsLoadState("failed");
      }
      setFeedback("actionFailure");
    } finally {
      setIsSaving(false);
    }
  }

  async function checkConnection() {
    setIsTesting(true);
    setFeedback(null);
    try {
      const result = await testAiConnection("gemini");
      setFeedback(result.ok ? "testSuccess" : "testFailure");
    } catch {
      setFeedback("testFailure");
    } finally {
      setIsTesting(false);
    }
  }

  async function removeKey() {
    const hadPendingSettingsLoad = settingsLoadState === "loading";
    settingsRequestGeneration.current += 1;
    setIsDeleting(true);
    setFeedback(null);
    try {
      const settings = await deleteAiApiKey("gemini");
      setConfigured(settings.configured);
      setSettingsLoadState("ready");
    } catch {
      if (hadPendingSettingsLoad) {
        setConfigured(null);
        setSettingsLoadState("failed");
      }
      setFeedback("actionFailure");
    } finally {
      setIsDeleting(false);
    }
  }

  const isWorking = isSaving || isTesting || isDeleting;
  const actionsDisabled = !connectionReady || isWorking;
  const status = !connectionReady
    ? ai.connecting
    : settingsLoadState === "failed"
      ? ai.settingsLoadFailure
      : settingsLoadState === "loading"
        ? ai.loading
        : configured === true
      ? ai.configured
      : configured === false
        ? ai.notConfigured
        : ai.loading;

  return (
    <Card className="border-blue-100 bg-white/95 shadow-sm">
      <CardHeader className="pb-4">
        <CardTitle className="text-xl text-blue-950">{ai.title}</CardTitle>
        <CardDescription className="leading-6 text-blue-950/65">{ai.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-lg bg-blue-50 px-3 py-2 text-sm font-medium text-blue-950">{status}</div>
        {connectionReady && settingsLoadState === "failed" ? (
          <Button variant="outline" className="border-blue-200 text-blue-950 hover:bg-blue-50" onClick={loadSettings} disabled={isWorking}>
            {ai.retrySettingsLoad}
          </Button>
        ) : null}
        <div className="space-y-2">
          <Label htmlFor="gemini-api-key">{ai.apiKeyLabel}</Label>
          <Input
            id="gemini-api-key"
            type="password"
            autoComplete="off"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            disabled={actionsDisabled}
          />
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          <Button
            className="bg-blue-950 text-white hover:bg-blue-900"
            onClick={saveKey}
            disabled={actionsDisabled || !apiKey.trim()}
          >
            {ai.save}
          </Button>
          <Button variant="outline" className="border-blue-200 text-blue-950 hover:bg-blue-50" onClick={checkConnection} disabled={actionsDisabled}>
            {ai.test}
          </Button>
          <Button variant="outline" className="border-red-200 text-red-700 hover:bg-red-50" onClick={removeKey} disabled={actionsDisabled || configured !== true}>
            {ai.delete}
          </Button>
        </div>
        {feedback ? (
          <p className={feedback === "testSuccess" ? "text-sm text-emerald-700" : "text-sm text-red-700"} role="status">
            {ai[feedback]}
          </p>
        ) : null}
        <p className="text-sm leading-6 text-blue-950/65">{ai.privacyDisclosure}</p>
      </CardContent>
    </Card>
  );
}
