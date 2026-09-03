# Form Converter Field Test Runbook

This is an explicit, manual field test for scanned DMC forms. It submits each
PDF directly from the local sidecar to Gemini and is not part of automated
testing. Never commit PDFs, generated reports, or API keys.

## Inputs Needed

- One blank DMC student-history form for template review.
- 10-20 scanned PDFs with real handwriting for the first accuracy pass.
- Larger real-scan batches for 100, 1,000, and 5,000-page performance checks.
- A Gemini API key supplied only for the current field-test process.

The field-test script does not read, write, or delete Windows Credential
Manager entries. Prefer `GEMINI_API_KEY` over `--gemini-api-key`, because
command-line arguments can be visible to other local processes and shell
history.

## 1. Prepare Local Files

Put scanned PDFs in a private folder outside the repository, for example:

```powershell
C:\dmc-field-test\form-pdfs
```

The OCR cache is stored locally under `.dmc-assistant-data\ocr\gemini` (or the
directory selected by `DMC_DATA_DIR`). The field-test review output defaults to
`.dmc-field-tests\form-converter\<timestamp>`. Both can contain student PII;
the latter is ignored by Git and must remain private.

## 2. Run the Opt-in Gemini Test

From the repository root, set a process-local environment variable and run the
tool. Do not paste a real key into a shared terminal transcript.

```powershell
cd C:\dmc
$env:GEMINI_API_KEY = "<key-from-google-ai-studio>"
corepack pnpm run form-converter:field-test -- `
  --pdf-dir "C:\dmc-field-test\form-pdfs" `
  --output-dir "C:\dmc-field-test\results\pilot-001"
Remove-Item Env:GEMINI_API_KEY
```

`--gemini-api-key` is available for a one-off invocation, but the environment
variable is safer. The runner creates an in-memory credential store only for
that process; it does not call the desktop credential store or persist the
field-test key.

For each PDF, standard output contains only the local output path, page count,
model, processing mode, and Gemini usage totals. It never prints the key or
raw provider errors. `summary.json` and `quality-summary.csv` carry those
metrics; `field-results.csv` holds extracted values for manual review.

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

## 4. What the Test Preserves

The local Gemini OCR path retains page estimation, standard or batch processing,
structured JSON cache reuse, and usage metadata. A cache hit avoids a duplicate
submission for unchanged input unless the normal OCR request is forced to
refresh. Review all extracted fields before Excel export; this tool never
submits data to DMC.

## Pass Criteria Before Broad Release

- At least 10-20 real forms complete without local provider errors.
- Required fields are usable after review at the agreed accuracy target.
- Export schema matches the school workflow.
- 100-page batch has acceptable runtime and memory; larger 1,000 and 5,000-page
  runs either complete or give an understandable batching limit.
- No API key is present in local reports, cache files, diagnostics, or console
  output.

Automated tests use fakes and never call Gemini. Provider connectivity is
verified only by this deliberate, key-supplied field-test command.
