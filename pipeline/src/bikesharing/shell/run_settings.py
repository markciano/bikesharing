"""Reads the run settings file once, so the run and the Modal app share its values.

The core parses and checks the settings; this module only reads the package's
``run_settings.json``. The file sits next to ``core/settings.py`` so that Terraform
reads the same values (d009 #9, one data file for the pipeline's run settings).
"""

import json
from importlib import resources
from typing import Final

from bikesharing.core.settings import RunSettings, parse_run_settings

RUN_SETTINGS: Final[RunSettings] = parse_run_settings(
    json.loads(
        resources.files("bikesharing.core")
        .joinpath("run_settings.json")
        .read_text(encoding="utf-8")
    )
)
"""The run's cadence, time budget, timeout and container memory."""
