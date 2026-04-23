from __future__ import annotations

from pathlib import Path

from dmc_sidecar import config


def test_default_data_dir_prefers_env_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DMC_DATA_DIR", str(tmp_path / "sidecar-data"))

    assert config.default_data_dir() == tmp_path / "sidecar-data"


def test_packaged_resource_paths_use_bundled_resources_dir(monkeypatch, tmp_path: Path) -> None:
    bundled_root = tmp_path / "bundle"
    monkeypatch.setenv("DMC_BUNDLED_RESOURCES_DIR", str(bundled_root))

    assert config.config_signing_keys_path() == bundled_root / "shared-schemas" / "config-signing" / "keys.json"
    assert config.module_configs_root() == bundled_root / "module-configs"
