import messages from "../i18n/th.json";

const accountErrors = messages.app.account.errors as Record<string, string>;

export function describeAccountCode(code: string | null | undefined): string | null {
  if (!code) {
    return null;
  }
  return accountErrors[code] ?? null;
}

export function describeUserFacingError(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error);
  for (const [code, message] of Object.entries(accountErrors)) {
    if (raw.includes(code)) {
      return message;
    }
  }
  return raw;
}
