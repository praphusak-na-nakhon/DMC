from __future__ import annotations

from .gemini_ocr import (
    GEMINI_OCR_CREDITS_PER_PAGE,
    GEMINI_OCR_MODEL,
    GeminiOcrDmcFormRequest,
    GeminiOcrDmcFormResponse,
    GeminiOcrPreparation,
    ocr_dmc_form_with_gemini,
    prepare_gemini_ocr_request,
)


# Backward-compatible aliases for builds that still use the previous
# AksonOCR-named Python imports or RPC method.
AKSON_OCR_CREDITS_PER_PAGE = GEMINI_OCR_CREDITS_PER_PAGE
AKSON_OCR_MODEL = GEMINI_OCR_MODEL
AksonOcrDmcFormRequest = GeminiOcrDmcFormRequest
AksonOcrDmcFormResponse = GeminiOcrDmcFormResponse
AksonOcrPreparation = GeminiOcrPreparation
prepare_akson_ocr_request = prepare_gemini_ocr_request
ocr_dmc_form_with_akson = ocr_dmc_form_with_gemini
