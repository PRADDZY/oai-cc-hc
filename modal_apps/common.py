from __future__ import annotations

import subprocess
from pathlib import Path

import modal

APP_PREFIX = "flood-rescue"
DATA_VOLUME_NAME = "flood-rescue-data"
MODEL_VOLUME_NAME = "flood-rescue-models"
RUN_VOLUME_NAME = "flood-rescue-runs"

DATA_PATH = Path("/vol/data")
MODEL_PATH = Path("/vol/models")
RUN_PATH = Path("/vol/runs")


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def base_image() -> modal.Image:
    return (
        modal.Image.debian_slim(python_version="3.13")
        .pip_install("fastapi>=0.115,<1", "pydantic>=2.10,<3")
        .add_local_python_source("rescue_swarm")
    )


def training_image() -> modal.Image:
    return base_image().pip_install("numpy>=2.1,<3")


data_volume = modal.Volume.from_name(DATA_VOLUME_NAME, create_if_missing=True)
model_volume = modal.Volume.from_name(MODEL_VOLUME_NAME, create_if_missing=True)
run_volume = modal.Volume.from_name(RUN_VOLUME_NAME, create_if_missing=True)
