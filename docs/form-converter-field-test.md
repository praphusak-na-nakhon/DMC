# Form Converter Field Test Runbook

This runbook covers the remaining manual validation for the scanned PDF form
converter. It is intentionally separate from unit tests because it requires real
school forms and, when `DMC_OCR_PROVIDER=openai`, a real AI API key.

## Inputs Needed

- One blank DMC student-history form.
- 10-20 scanned PDFs with real handwriting for the first accuracy pass.
- Larger scan batches for performance: 100 pages, 1,000 pages, and later 5,000 pages.
- A cloud staging user with enough credits.
- `DMC_OCR_OPENAI_API_KEY` when testing the OpenAI provider.
- `DMC_OCR_GEMINI_API_KEY` when testing the Gemini provider.

## 1. Real Document Test

Put scanned PDFs in a local folder that is not committed, for example:

```powershell
C:\dmc-field-test\form-pdfs
```

The field-test script writes local review files only. `field-results.csv` may
contain student PII, so keep the output folder private and do not commit it.

## 2. Enable AI Provider

In the cloud staging terminal:

```powershell
cd C:\dmc
$env:DMC_CLOUD_BASE_URL = "http://127.0.0.1:8000"
$env:DMC_OCR_PROVIDER = "openai"
$env:DMC_OCR_OPENAI_API_KEY = "<your-api-key>"
$env:DMC_OCR_OPENAI_MODEL = "gpt-5.5"
corepack pnpm run cloud:dev
```

For mock-only workflow checks, keep `DMC_OCR_PROVIDER=mock`.

Gemini staging example:

```powershell
cd C:\dmc
$env:DMC_CLOUD_BASE_URL = "http://127.0.0.1:8000"
$env:DMC_OCR_PROVIDER = "gemini"
$env:DMC_OCR_GEMINI_API_KEY = "<key-from-google-ai-studio>"
$env:DMC_OCR_GEMINI_MODEL = "gemini-2.5-flash-lite"
corepack pnpm run cloud:dev
```

## 3. Template Mapping Review

Current v1 mapping is `student_history_v1`:

| Field | Required | Export column |
|---|---:|---|
| student_id | yes | student_id |
| first_name | yes | first_name |
| last_name | yes | last_name |
| birth_date | no | birth_date |
| phone | no | phone |
| address | no | address |

After reviewing the blank form, update `apps/sidecar/dmc_sidecar/form_template.py`
if the real form needs more fields or different validation.

## 4. Run Accuracy/Performance Batch

Start cloud staging, then run:

```powershell
cd C:\dmc
$env:DMC_FIELD_TEST_EMAIL = "teacher@example.test"
$env:DMC_FIELD_TEST_PASSWORD = "correct-password"
corepack pnpm run form-converter:field-test -- `
  --pdf-dir "C:\dmc-field-test\form-pdfs" `
  --cloud-base-url "http://127.0.0.1:8000" `
  --output-dir "C:\dmc-field-test\results\pilot-001"
```

Outputs:

- `quality-summary.csv` has one row per PDF with page count, record count,
  status counts, and average confidence.
- `field-results.csv` has OCR field values and alternatives for manual review.
- `summary.json` has the same quality metrics in JSON.

The script reserves credits before OCR and releases them after each test file.
Provider costs may still apply when using a real AI provider.

## Pass Criteria Before Production Work

- At least 10-20 real forms processed without OCR gateway errors.
- Required fields are usable after review for at least the agreed target accuracy.
- Export schema matches the Excel file expected by the school workflow.
- 100-page batch completes with acceptable runtime and memory.
- 1,000-page batch completes or produces a clear batching limit.
- No PII appears in cloud telemetry, admin audit, or ledger records.
