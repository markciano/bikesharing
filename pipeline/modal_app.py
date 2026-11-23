"""Platform module: the Modal app of the scheduled function, deployed with every credential of production.

This is the only app the deploy script deploys. The one-off function lives in
``modal_one_off.py``, an app of its own, so that ``modal run`` never creates this
function (d008 DI12, Environments and configuration). The module calls the shell's
``run`` and nothing else, and does not import the engine (ADR-0046, Functional core
and imperative shell for the pipeline, rules 1 and 4). The deploy script runs it with
the ``platform`` dependency group, which the checks never install.
"""

import os

import modal

from bikesharing.core.settings import schedule_cron
from bikesharing.shell.run import run, scheduled_config
from bikesharing.shell.run_settings import RUN_SETTINGS
from modal_image import (
    BRONZE_READ_SECRET,
    DEPLOY_SECRET,
    HEARTBEAT_SECRET,
    LAKEHOUSE_WRITE_SECRET,
    MEMORY_MIB,
    MONITORING_SECRET,
    REMOTE_ROOT,
    TIMEOUT_S,
    image,
    raise_if_failed,
    secret,
)

APP_NAME = "bikesharing-pipeline"
CRON = schedule_cron(RUN_SETTINGS)

app = modal.App(APP_NAME)


@app.function(
    image=image,
    schedule=modal.Cron(CRON),
    secrets=[
        secret(BRONZE_READ_SECRET),
        secret(LAKEHOUSE_WRITE_SECRET),
        secret(DEPLOY_SECRET),
        secret(HEARTBEAT_SECRET),
        secret(MONITORING_SECRET),
    ],
    cpu=1.0,
    memory=(MEMORY_MIB, MEMORY_MIB),
    timeout=TIMEOUT_S,
    max_containers=1,
)
def scheduled_run() -> None:
    """Run the pipeline on its schedule, with every credential of production.

    Raises
    ------
    ValueError
        If the image holds no code version.
    RuntimeError
        If the run failed.
    """
    config = scheduled_config(
        os.environ, root=REMOTE_ROOT, container_memory_mib=MEMORY_MIB
    )
    raise_if_failed(run(config))
