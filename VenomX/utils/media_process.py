"""Run short playback helpers off the event loop, explicitly waiting for each PID."""
import asyncio
import os
import signal
import subprocess
from threading import Event
from time import monotonic


async def run_media_process(command, timeout, *, stderr=subprocess.DEVNULL):
    cancelled = Event()
    deadline = monotonic() + timeout

    def run():
        if cancelled.is_set() or monotonic() >= deadline:
            raise TimeoutError("Media helper deadline exceeded")
        with subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=stderr,
            start_new_session=True,
        ) as proc:
            try:
                while not cancelled.is_set():
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        break
                    try:
                        output, errors = proc.communicate(timeout=min(0.25, remaining))
                        return proc.returncode, output, errors
                    except subprocess.TimeoutExpired:
                        continue
                raise TimeoutError("Media helper deadline exceeded")
            finally:
                if proc.returncode is None:
                    # A resolver child may still hold its parent's output pipe.
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    proc.wait()

    worker = asyncio.create_task(asyncio.to_thread(run))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        cancelled.set()
        await asyncio.gather(worker, return_exceptions=True)
        raise
