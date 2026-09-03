from __future__ import annotations

import json
from pathlib import Path
from urllib import request

import pytest

from dmc_sidecar import config, module_config
from dmc_sidecar.errors import DomainError


def bundled_payload() -> dict[str, object]:
    return {
        "module": "graduation", "version": "1",
        "login_url": "https://example.test/login",
        "target_url_template": "https://example.test/students?level={level_code}",
        "selectors": {}, "status_code_map": {}, "level_rules": {},
    }


def write_bundle(monkeypatch, tmp_path: Path, raw: str) -> None:
    monkeypatch.setenv("DMC_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(config, "module_configs_root", lambda: tmp_path)
    module_dir = tmp_path / "graduation"
    module_dir.mkdir()
    (module_dir / "v1.json").write_text(raw, encoding="utf-8")


def test_bundled_graduation_config_loads_without_cloud_or_signature(monkeypatch, tmp_path: Path) -> None:
    write_bundle(monkeypatch, tmp_path, json.dumps(bundled_payload()))
    monkeypatch.setenv("DMC_CLOUD_BASE_URL", "https://cloud.example.test")

    def no_network(*args, **kwargs):
        pytest.fail("bundled config must not make a network request")

    monkeypatch.setattr(request, "urlopen", no_network)
    payload = module_config.load_bundled_module_config("graduation")
    assert payload["login_url"] == "https://example.test/login"
    assert payload["version"] == "1"
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize("raw", ["{not-json", "[]", "null", "{}"])
def test_bundled_config_rejects_invalid_document(monkeypatch, tmp_path: Path, raw: str) -> None:
    write_bundle(monkeypatch, tmp_path, raw)
    with pytest.raises(DomainError, match="CONFIG_BUNDLED_INVALID"):
        module_config.load_bundled_module_config("graduation")


@pytest.mark.parametrize(("field", "value"), [
    ("module", "currentStudents"), ("version", 1), ("login_url", None),
    ("selectors", {"student_rows": 1}), ("status_code_map", {"status": 201}),
    ("level_rules", {"ม.3": {"level_code": "12"}}),
    ("level_rules", {"ม.3": {"level_code": "12", "default_missing_code": None,
                            "ambiguity_floor": None, "require_exact_student_no": "false"}}),
    ("unexpected", True),
])
def test_bundled_config_rejects_wrong_types_and_unknown_fields(monkeypatch, tmp_path: Path, field: str, value: object) -> None:
    payload = bundled_payload()
    payload[field] = value
    write_bundle(monkeypatch, tmp_path, json.dumps(payload))
    with pytest.raises(DomainError, match="CONFIG_BUNDLED_INVALID"):
        module_config.load_bundled_module_config("graduation")


def test_missing_bundled_file_is_actionable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "module_configs_root", lambda: tmp_path)
    with pytest.raises(DomainError, match="CONFIG_BUNDLED_INVALID"):
        module_config.load_bundled_module_config("graduation")


@pytest.mark.parametrize("module", ["currentStudents", "../graduation", ""])
def test_unknown_module_is_rejected(monkeypatch, tmp_path: Path, module: str) -> None:
    write_bundle(monkeypatch, tmp_path, json.dumps(bundled_payload()))
    with pytest.raises(DomainError, match="CONFIG_BUNDLED_INVALID"):
        module_config.load_bundled_module_config(module)


def test_shipped_graduation_payload_is_preserved() -> None:
    payload = module_config.load_bundled_module_config("graduation")
    assert payload == json.loads((config.module_configs_root() / "graduation" / "v1.json").read_text(encoding="utf-8"))
    assert payload["version"] == "0.1.0"
