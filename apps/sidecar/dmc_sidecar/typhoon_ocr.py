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


# Backward-compatible aliases for builds that still use the old Typhoon-named
# Python imports or RPC method.
TYPHOON_OCR_CREDITS_PER_PAGE = GEMINI_OCR_CREDITS_PER_PAGE
TYPHOON_OCR_MODEL = GEMINI_OCR_MODEL
TyphoonOcrDmcFormRequest = GeminiOcrDmcFormRequest
TyphoonOcrDmcFormResponse = GeminiOcrDmcFormResponse
TyphoonOcrPreparation = GeminiOcrPreparation
prepare_typhoon_ocr_request = prepare_gemini_ocr_request
ocr_dmc_form_with_typhoon = ocr_dmc_form_with_gemini
