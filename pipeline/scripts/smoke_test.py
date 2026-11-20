"""Post-deploy smoke test: run the deployed scheduled function once and wait for it.

The deploy script runs it with the ``platform`` dependency group, once the app is
deployed (d008, Deploy script). The run is a normal production run: it is idempotent,
waits behind a scheduled run in progress (``max_containers=1``) and sends its
heartbeat signal like any other. The function raises when the run fails, so the call
ends failed and this script exits with 1. The call's ID, printed before the wait, finds
the run's events in Modal's logs. The wait has no timeout of its own: the function's
timeout bounds the run in progress it may wait behind, and then its own run, so it
ends in about twice that timeout at most.
"""

import sys

import modal

# The names `modal_app.py` gives the app and its scheduled function; importing that
# module here would build its image.
APP_NAME = "bikesharing-pipeline"
FUNCTION_NAME = "scheduled_run"


def main() -> int:
    """Invoke the deployed scheduled function and wait for its result.

    Returns
    -------
    int
        0 if the run ended without failing, 1 if the function could not be started
        or its call failed.
    """
    try:
        function = modal.Function.from_name(APP_NAME, FUNCTION_NAME)
        call = function.spawn()
        print(f"smoke test: call {call.object_id}", flush=True)
        call.get()
    # Whatever fails, whether Modal's lookup or the run's own exception, must end the
    # deployment with a message and the call's ID, not with a traceback.
    except Exception as error:  # noqa: BLE001
        print(f"smoke test failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print("smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
