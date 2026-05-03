# P-SAR Readiness Dashboard

The P-SAR readiness feature is implemented as a local desktop/sidecar workflow.
The desktop calls JSON-RPC methods instead of REST routes because this app's
existing backend boundary is the Python sidecar.

## Backend flow

- `get_psar_readiness` returns readiness for a project ID.
- `add_psar_evidence` validates a local evidence file, stores file metadata in
  the local reports directory, maps the file to the fixed P-SAR matrix, and
  returns an updated readiness response.
- `generate_psar_report` writes a local `.docx` from the official
  `P-SAR-form.docx` template. It preserves the template package and patches only
  fillable text locations that can be derived from current readiness data.
- The deterministic scoring logic lives in `dmc_sidecar.p_sar_readiness`.

The requirement matrix is fixed in code and is based on the supplied
`P-SAR-form.docx` structure:

- Part 1: basic information, teaching assignment, learner assessment, and
  teaching practice evidence.
- Part 2: professional development and recognition.
- Part 3: improvement plan and support needs.
- Appendix: evidence for Standards 1, 2, and 3.

## Scoring rules

- Complete requires enough accepted evidence at or above the confidence
  threshold.
- Partial means some accepted evidence exists but not enough.
- Missing means no evidence is mapped to the requirement.
- Needs review means evidence exists but confidence is low or the mapping is
  ambiguous.
- Overall readiness is a weighted average across all requirements.

Default thresholds:

- Evidence confidence: `0.75`
- Report readiness warning: `0.8`

## AI mapping extension point

The service includes `build_ai_evidence_mapping_prompt(...)` for future AI
classification. AI output should map uploaded evidence to the fixed matrix only;
it must not add or redefine P-SAR requirements.

## Current generation scope

The generated `.docx` is based on the official form and must not introduce a new
layout. Because the supplied template does not contain Word content controls, the
sidecar performs conservative OOXML patching:

- fields with no reviewed structured value remain blank in the original form;
- Part 3 recommendation lines are filled from deterministic readiness gaps;
- the generator must not fabricate teacher, school, or assessment values.

The next production step is to add reviewed structured extraction values for the
remaining form fields, then map those values into the original table cells and
paragraph blanks.
