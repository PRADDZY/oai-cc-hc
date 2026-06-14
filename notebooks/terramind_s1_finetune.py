"""Colab-friendly TerraMind S1 fine-tuning entrypoint.

This file intentionally imports no heavy ML dependencies at module import time.
Install the `perception` optional dependencies in Colab before calling `main`.
"""

MODEL_ID = "ibm-esa-geospatial/TerraMind-1.0-tiny"
MODEL_REVISION = "2b5ac0a"


def main() -> dict[str, str]:
    return {
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "default_modality": "S1GRD",
        "training_stage": "frozen-backbone-then-final-blocks",
    }


if __name__ == "__main__":
    print(main())

