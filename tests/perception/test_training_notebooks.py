import runpy
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "path",
    [
        Path("notebooks/terramind_s1_finetune.py"),
        Path("notebooks/uav_detector_finetune.py"),
    ],
)
def test_training_notebook_imports_without_optional_dependencies(path: Path) -> None:
    namespace = runpy.run_path(path, run_name="notebook_test")

    assert callable(namespace["main"])


def test_terramind_notebook_pins_model_revision() -> None:
    namespace = runpy.run_path(
        Path("notebooks/terramind_s1_finetune.py"),
        run_name="notebook_test",
    )

    assert namespace["MODEL_REVISION"] == "2b5ac0a"
