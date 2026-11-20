"""Platform module: the Modal app of the one-off function, which holds bronze's read-only credential only.

It is an app of its own, started with ``modal run``, so that a run from a branch never
creates the scheduled function and its production credentials (d008 DI12,
Environments and configuration). It does not import ``modal_app``, and it names no
Secret but bronze's. The module calls the shell's ``run`` and nothing else, and does
not import the engine (ADR-0046, Functional core and imperative shell for the
pipeline, rules 1 and 4). It runs with the ``platform`` dependency group, which the
checks never install.
"""

import os

import modal

from bikesharing.shell.run import one_off_config, run
from modal_image import (
    BRONZE_READ_SECRET,
    MEMORY_MIB,
    REMOTE_ROOT,
    TIMEOUT_S,
    image,
    raise_if_failed,
    secret,
)

APP_NAME = "bikesharing-pipeline-one-off"

app = modal.App(APP_NAME)


@app.function(
    image=image,
    secrets=[secret(BRONZE_READ_SECRET)],
    cpu=1.0,
    memory=(MEMORY_MIB, MEMORY_MIB),
    timeout=TIMEOUT_S,
)
def one_off_run() -> None:
    """Run the pipeline once, over bronze's read-only credentials.

    It keeps its tables on the container's disk, publishes nothing and sends no
    heartbeat, so a run from a branch can neither write to production nor deploy the
    page.

    Raises
    ------
    RuntimeError
        If the run failed.
    """
    config = one_off_config(
        os.environ, root=REMOTE_ROOT, container_memory_mib=MEMORY_MIB
    )
    raise_if_failed(run(config))
