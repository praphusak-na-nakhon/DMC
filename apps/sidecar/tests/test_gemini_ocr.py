from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pypdf import PdfWriter

from dmc_sidecar import config
from dmc_sidecar.errors import DomainError
from dmc_sidecar.gemini_ocr import (
    GEMINI_OCR_MODEL,
    GeminiOcrDmcFormRequest,
    GeminiOcrUsageMetadata,
    _generate_structured_json_with_gemini,
    _generate_structured_json_with_gemini_batch,
    ocr_dmc_form_with_gemini,
)


def _pdf_with_pages(page_count: int) -> bytes:
    stream = BytesIO()
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=72, height=72)
    writer.write(stream)
    return stream.getvalue()


def test_gemini_upload_uses_files_api_and_generate_content(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "form.pdf"
    source_path.write_bytes(_pdf_with_pages(1))
    captured: dict[str, Any] = {}

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeTypes:
        GenerateContentConfig = FakeGenerateContentConfig

    class FakeFiles:
        def upload(self, *, file: str, config: dict[str, object]) -> object:
            captured["upload_file"] = file
            captured["upload_config"] = config
            return SimpleNamespace(name="files/form", state="ACTIVE")

        def delete(self, *, name: str) -> None:
            captured["deleted_name"] = name

    class FakeModels:
        def generate_content(self, *, model: str, contents: list[object], config: object) -> object:
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config
            return SimpleNamespace(
                text='{"schema_version":"dmc_assistant_structured_ocr.v1","records":[{"record_type":"dmc_form","fields":{"citizen_id":"1810800164491"}}]}',
                usage_metadata=SimpleNamespace(
                    prompt_token_count=1200,
                    candidates_token_count=400,
                    total_token_count=1600,
                ),
            )

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            captured["api_key"] = api_key
            self.files = FakeFiles()
            self.models = FakeModels()
            self.closed = False

        def close(self) -> None:
            captured["closed"] = True

    fake_genai = SimpleNamespace(Client=FakeClient)
    monkeypatch.setattr("dmc_sidecar.gemini_ocr._load_google_genai", lambda: (fake_genai, FakeTypes))

    payload, usage = _generate_structured_json_with_gemini(
        source_path,
        api_key="secret",
        model=GEMINI_OCR_MODEL,
        pages_estimated=2,
    )

    assert captured["api_key"] == "secret"
    assert captured["upload_file"] == str(source_path)
    assert captured["upload_config"] == {"mime_type": "application/pdf"}
    assert captured["model"] == "gemini-3.5-flash"
    assert captured["contents"][0].name == "files/form"
    assert "compact JSON" in captured["contents"][1]
    assert captured["config"].kwargs == {
        "temperature": 0,
        "response_mime_type": "application/json",
    }
    assert captured["deleted_name"] == "files/form"
    assert captured["closed"] is True
    assert payload["records"][0]["fields"]["citizen_id"] == "1810800164491"
    assert usage is not None
    assert usage.prompt_token_count == 1200
    assert usage.total_tokens_per_page == 800


def test_gemini_batch_uses_jsonl_input_file_and_downloads_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "form.pdf"
    source_path.write_bytes(_pdf_with_pages(1))
    captured: dict[str, Any] = {}

    class FakeUploadFileConfig:
        def __init__(self, *, display_name: str, mime_type: str) -> None:
            self.display_name = display_name
            self.mime_type = mime_type

    class FakeTypes:
        UploadFileConfig = FakeUploadFileConfig

    class FakeFiles:
        def upload(self, *, file: str, config: object) -> object:
            uploads = captured.setdefault("uploads", [])
            assert isinstance(uploads, list)
            uploads.append((file, config))
            if file.endswith(".jsonl"):
                captured["jsonl_request"] = Path(file).read_text(encoding="utf-8")
                return SimpleNamespace(name="files/batch-input", uri="https://generativelanguage.googleapis.com/v1beta/files/batch-input", state="ACTIVE")
            return SimpleNamespace(name="files/form", uri="https://generativelanguage.googleapis.com/v1beta/files/form", state="ACTIVE")

        def delete(self, *, name: str) -> None:
            deleted_names = captured.setdefault("deleted_names", [])
            assert isinstance(deleted_names, list)
            deleted_names.append(name)

        def download(self, *, file: str) -> bytes:
            captured["download_file"] = file
            return (
                b'{"key":"dmc-ocr-source","response":{"candidates":[{"content":{"parts":[{"text":"'
                b'{\\"schema_version\\":\\"dmc_assistant_structured_ocr.v1\\",\\"records\\":[{\\"record_type\\":\\"dmc_form\\",\\"fields\\":{\\"citizen_id\\":\\"1810800164491\\"}}]}'
                b'"}]}}],"usageMetadata":{"promptTokenCount":1000,"candidatesTokenCount":300,"totalTokenCount":1300}}}\n'
            )

    class FakeBatches:
        def create(self, *, model: str, src: str, config: dict[str, object]) -> object:
            captured["model"] = model
            captured["src"] = src
            captured["config"] = config
            return SimpleNamespace(name="batches/ocr-1", state=SimpleNamespace(name="JOB_STATE_PENDING"))

        def get(self, *, name: str) -> object:
            captured["polled_name"] = name
            return SimpleNamespace(
                name=name,
                state=SimpleNamespace(name="JOB_STATE_SUCCEEDED"),
                dest=SimpleNamespace(file_name="files/batch-result"),
            )

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            captured["api_key"] = api_key
            self.files = FakeFiles()
            self.batches = FakeBatches()
            self.closed = False

        def close(self) -> None:
            captured["closed"] = True

    fake_genai = SimpleNamespace(Client=FakeClient)
    monkeypatch.setattr("dmc_sidecar.gemini_ocr._load_google_genai", lambda: (fake_genai, FakeTypes))
    monkeypatch.setattr("dmc_sidecar.gemini_ocr.time.sleep", lambda _: None)

    payload, usage, batch_job_name, batch_state = _generate_structured_json_with_gemini_batch(
        source_path,
        api_key="secret",
        model="gemini-3.5-flash",
        pages_estimated=1,
    )

    assert captured["api_key"] == "secret"
    uploads = captured["uploads"]
    assert isinstance(uploads, list)
    assert uploads[0] == (str(source_path), {"mime_type": "application/pdf"})
    assert isinstance(uploads[1][1], FakeUploadFileConfig)
    assert uploads[1][1].mime_type == "jsonl"
    assert captured["model"] == "gemini-3.5-flash"
    assert captured["src"] == "files/batch-input"
    jsonl_request = json.loads(str(captured["jsonl_request"]).strip())
    assert jsonl_request["key"] == "dmc-ocr-pages-0001-0001"
    assert jsonl_request["request"]["contents"][0]["parts"][0]["file_data"]["file_uri"].endswith("/files/form")
    assert jsonl_request["request"]["generation_config"] == {
        "temperature": 0,
        "response_mime_type": "application/json",
    }
    assert captured["polled_name"] == "batches/ocr-1"
    assert captured["download_file"] == "files/batch-result"
    assert captured["deleted_names"] == ["files/form", "files/batch-input", "files/batch-result"]
    assert captured["closed"] is True
    assert batch_job_name == "batches/ocr-1"
    assert batch_state == "JOB_STATE_SUCCEEDED"
    assert payload["records"][0]["fields"]["citizen_id"] == "1810800164491"
    assert usage is not None
    assert usage.total_token_count == 1300


def test_gemini_batch_splits_multi_page_pdf_into_page_pair_requests(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "forms.pdf"
    source_path.write_bytes(_pdf_with_pages(4))
    captured: dict[str, Any] = {}

    class FakeUploadFileConfig:
        def __init__(self, *, display_name: str, mime_type: str) -> None:
            self.display_name = display_name
            self.mime_type = mime_type

    class FakeTypes:
        UploadFileConfig = FakeUploadFileConfig

    class FakeFiles:
        def upload(self, *, file: str, config: object) -> object:
            uploads = captured.setdefault("uploads", [])
            assert isinstance(uploads, list)
            uploads.append((file, config))
            if file.endswith(".jsonl"):
                captured["jsonl_request"] = Path(file).read_text(encoding="utf-8")
                return SimpleNamespace(name="files/batch-input", uri="https://generativelanguage.googleapis.com/v1beta/files/batch-input", state="ACTIVE")
            upload_index = sum(1 for uploaded_file, _config in uploads if str(uploaded_file).endswith(".pdf"))
            return SimpleNamespace(
                name=f"files/form-{upload_index}",
                uri=f"https://generativelanguage.googleapis.com/v1beta/files/form-{upload_index}",
                state="ACTIVE",
            )

        def delete(self, *, name: str) -> None:
            deleted_names = captured.setdefault("deleted_names", [])
            assert isinstance(deleted_names, list)
            deleted_names.append(name)

        def download(self, *, file: str) -> bytes:
            captured["download_file"] = file
            lines = [
                {
                    "key": "dmc-ocr-pages-0001-0002",
                    "response": {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {
                                            "text": json.dumps(
                                                {
                                                    "schema_version": "dmc_assistant_structured_ocr.v1",
                                                    "document_type": "dmc_form",
                                                    "records": [
                                                        {
                                                            "record_type": "dmc_form",
                                                            "page_start": 1,
                                                            "page_end": 2,
                                                            "fields": {"citizen_id": "1810800164491"},
                                                        }
                                                    ],
                                                }
                                            )
                                        }
                                    ]
                                }
                            }
                        ],
                        "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 300, "totalTokenCount": 1300},
                    },
                },
                {
                    "key": "dmc-ocr-pages-0003-0004",
                    "response": {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {
                                            "text": json.dumps(
                                                {
                                                    "schema_version": "dmc_assistant_structured_ocr.v1",
                                                    "document_type": "dmc_form",
                                                    "records": [
                                                        {
                                                            "record_type": "dmc_form",
                                                            "page_start": 1,
                                                            "page_end": 2,
                                                            "fields": {"citizen_id": "1810800164483"},
                                                        }
                                                    ],
                                                }
                                            )
                                        }
                                    ]
                                }
                            }
                        ],
                        "usageMetadata": {"promptTokenCount": 900, "candidatesTokenCount": 250, "totalTokenCount": 1150},
                    },
                },
            ]
            return ("\n".join(json.dumps(line) for line in lines) + "\n").encode("utf-8")

    class FakeBatches:
        def create(self, *, model: str, src: str, config: dict[str, object]) -> object:
            captured["model"] = model
            captured["src"] = src
            captured["config"] = config
            return SimpleNamespace(name="batches/ocr-2", state=SimpleNamespace(name="JOB_STATE_PENDING"))

        def get(self, *, name: str) -> object:
            captured["polled_name"] = name
            return SimpleNamespace(
                name=name,
                state=SimpleNamespace(name="JOB_STATE_SUCCEEDED"),
                dest=SimpleNamespace(file_name="files/batch-result"),
            )

    class FakeClient:
        def __init__(self, *, api_key: str) -> None:
            captured["api_key"] = api_key
            self.files = FakeFiles()
            self.batches = FakeBatches()

        def close(self) -> None:
            captured["closed"] = True

    fake_genai = SimpleNamespace(Client=FakeClient)
    monkeypatch.setattr("dmc_sidecar.gemini_ocr._load_google_genai", lambda: (fake_genai, FakeTypes))
    monkeypatch.setattr("dmc_sidecar.gemini_ocr.time.sleep", lambda _: None)

    payload, usage, batch_job_name, batch_state = _generate_structured_json_with_gemini_batch(
        source_path,
        api_key="secret",
        model="gemini-3.5-flash",
        pages_estimated=4,
    )

    uploads = captured["uploads"]
    assert isinstance(uploads, list)
    assert len(uploads) == 3
    assert str(uploads[0][0]).endswith("pages-0001-0002.pdf")
    assert str(uploads[1][0]).endswith("pages-0003-0004.pdf")
    assert isinstance(uploads[2][1], FakeUploadFileConfig)
    jsonl_lines = [json.loads(line) for line in str(captured["jsonl_request"]).splitlines()]
    assert [line["key"] for line in jsonl_lines] == ["dmc-ocr-pages-0001-0002", "dmc-ocr-pages-0003-0004"]
    assert "thinking_config" not in jsonl_lines[0]["request"]["generation_config"]
    assert "thinking_config" not in jsonl_lines[1]["request"]["generation_config"]
    assert "original pages 1-2" in jsonl_lines[0]["request"]["contents"][0]["parts"][1]["text"]
    assert "original pages 3-4" in jsonl_lines[1]["request"]["contents"][0]["parts"][1]["text"]
    assert batch_job_name == "batches/ocr-2"
    assert batch_state == "JOB_STATE_SUCCEEDED"
    assert payload["document_type"] == "dmc_form"
    assert [record["page_start"] for record in payload["records"]] == [1, 3]
    assert [record["page_end"] for record in payload["records"]] == [2, 4]
    assert usage is not None
    assert usage.prompt_token_count == 1900
    assert usage.candidates_token_count == 550
    assert usage.total_token_count == 2450
    assert usage.total_tokens_per_page == 612.5


def test_ocr_dmc_form_with_gemini_writes_structured_json_and_uses_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path / "data")
    source_path = tmp_path / "form.pdf"
    source_path.write_bytes(_pdf_with_pages(2))
    calls: list[Path] = []

    def fake_generate(
        source: Path,
        *,
        api_key: str,
        model: str,
        pages_estimated: int,
    ) -> tuple[dict[str, object], GeminiOcrUsageMetadata]:
        calls.append(source)
        assert source == source_path
        assert api_key == "secret"
        assert model == "gemini-3.5-flash"
        assert pages_estimated == 2
        return (
            {
                "schema_version": "dmc_assistant_structured_ocr.v1",
                "document_type": "dmc_form",
                "records": [
                    {
                        "record_type": "dmc_form",
                        "page_start": 1,
                        "page_end": 2,
                        "fields": {"citizen_id": "1810800164491", "student_no": "1069"},
                    }
                ],
            },
            GeminiOcrUsageMetadata(
                prompt_token_count=1290,
                candidates_token_count=600,
                total_token_count=1890,
                input_tokens_per_page=645,
                output_tokens_per_page=300,
                total_tokens_per_page=945,
            ),
        )

    monkeypatch.setattr("dmc_sidecar.gemini_ocr._generate_structured_json_with_gemini", fake_generate)

    response = ocr_dmc_form_with_gemini(
        GeminiOcrDmcFormRequest(
            source_path=str(source_path),
            api_key="secret",
            model="gemini-3.5-flash",
            processing_mode="standard",
        )
    )

    output_path = Path(response.markdown_path)
    assert response.engine == "gemini"
    assert response.processing_mode == "standard"
    assert response.output_format == "structured_json"
    assert response.structured_json_path == response.markdown_path
    assert response.cached is False
    assert response.pages_processed == 2
    assert response.pages_estimated == 2
    assert response.credits_per_page == 3
    assert response.credits_charged == 0
    assert response.charged is False
    assert response.average_confidence is None
    assert response.usage_metadata is not None
    assert response.usage_metadata.total_token_count == 1890
    assert output_path.suffix == ".json"
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["engine"] == "gemini"
    assert payload["model"] == "gemini-3.5-flash"
    assert payload["usage_metadata"]["total_token_count"] == 1890
    assert payload["records"][0]["fields"]["student_no"] == "1069"

    cached_response = ocr_dmc_form_with_gemini(
        GeminiOcrDmcFormRequest(source_path=str(source_path), model="gemini-3.5-flash", processing_mode="standard")
    )

    assert cached_response.cached is True
    assert cached_response.markdown_path == response.markdown_path
    assert cached_response.credits_charged == 0
    assert cached_response.usage_metadata is not None
    assert cached_response.usage_metadata.total_token_count == 1890
    assert calls == [source_path]


def test_ocr_dmc_form_with_gemini_adds_metadata_when_model_omits_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path / "data")
    source_path = tmp_path / "form.webp"
    source_path.write_bytes(b"not a real image but not opened by validation")
    monkeypatch.setattr(
        "dmc_sidecar.gemini_ocr._generate_structured_json_with_gemini",
        lambda source, *, api_key, model, pages_estimated: (
            {"records": [{"record_type": "dmc_form", "fields": {"citizen_id": "1810800164491"}}]},
            None,
        ),
    )

    response = ocr_dmc_form_with_gemini(
        GeminiOcrDmcFormRequest(source_path=str(source_path), api_key="secret", processing_mode="standard")
    )

    payload = json.loads(Path(response.markdown_path).read_text(encoding="utf-8"))
    assert payload["schema_version"] == "dmc_assistant_structured_ocr.v1"
    assert payload["engine"] == "gemini"
    assert response.pages_processed == 1


def test_ocr_dmc_form_with_gemini_requires_api_key_when_not_cached(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path / "data")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    source_path = tmp_path / "form.pdf"
    source_path.write_bytes(_pdf_with_pages(1))

    with pytest.raises(DomainError) as exc_info:
        ocr_dmc_form_with_gemini(GeminiOcrDmcFormRequest(source_path=str(source_path)))
    assert exc_info.value.code == "GEMINIOCR_API_KEY_REQUIRED"


def test_ocr_dmc_form_with_gemini_rejects_pdf_when_page_count_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path / "data")
    source_path = tmp_path / "form.pdf"
    source_path.write_bytes(b"%PDF-1.7\ncompressed or unsupported page tree\n%%EOF")

    with pytest.raises(DomainError) as exc_info:
        ocr_dmc_form_with_gemini(GeminiOcrDmcFormRequest(source_path=str(source_path), api_key="secret"))
    assert exc_info.value.code == "GEMINIOCR_PAGE_COUNT_UNKNOWN"


def test_ocr_dmc_form_with_gemini_maps_legacy_models_to_gemini(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(config, "default_data_dir", lambda: tmp_path / "data")
    source_path = tmp_path / "form.pdf"
    source_path.write_bytes(_pdf_with_pages(1))
    captured: dict[str, str] = {}

    def fake_generate(
        source: Path,
        *,
        api_key: str,
        model: str,
        pages_estimated: int,
    ) -> tuple[dict[str, object], None]:
        del source, api_key
        captured["model"] = model
        assert pages_estimated == 1
        return {"records": [{"record_type": "dmc_form", "fields": {"student_no": "1069"}}]}, None

    monkeypatch.setattr("dmc_sidecar.gemini_ocr._generate_structured_json_with_gemini", fake_generate)

    response = ocr_dmc_form_with_gemini(
        GeminiOcrDmcFormRequest(
            source_path=str(source_path),
            api_key="secret",
            model="AksonOCR-preview",
            processing_mode="standard",
        )
    )

    assert captured["model"] == "gemini-3.5-flash"
    assert response.model == "gemini-3.5-flash"
