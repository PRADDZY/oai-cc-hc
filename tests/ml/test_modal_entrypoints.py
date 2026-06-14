from __future__ import annotations

from pathlib import Path


def test_modal_entrypoints_exist() -> None:
    for path in (
        Path("modal_apps/prepare_data.py"),
        Path("modal_apps/perception_train.py"),
        Path("modal_apps/rl_train.py"),
        Path("modal_apps/evaluate.py"),
        Path("modal_apps/inference.py"),
    ):
        assert path.exists()
        assert "modal.App" in path.read_text(encoding="utf-8")
