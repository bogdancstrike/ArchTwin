"""Worker entrypoint: Temporal worker + outbox relay + reconcile loop (same image as the API)."""
from __future__ import annotations

import asyncio
import signal
from pathlib import Path

from temporalio.client import Client
from temporalio.worker import Worker

from archtwin.common.logging import configure, log
from archtwin.config import settings
from archtwin.worker import activities
from archtwin.worker.relay import reconcile_loop, run_relay
from archtwin.worker.workflows import DriftWorkflow, GraphBuildWorkflow, ScanWorkflow

ALIVE = Path("/tmp/archtwin-worker-alive")


async def heartbeat(stop: asyncio.Event) -> None:
    while not stop.is_set():
        ALIVE.write_text(str(asyncio.get_running_loop().time()))
        await asyncio.sleep(5)


async def main() -> None:
    s = settings()
    configure(s.log_level)
    for i in range(60):
        try:
            client = await Client.connect(s.temporal_address, namespace=s.temporal_namespace)
            break
        except Exception as e:  # noqa: BLE001
            log.warning("temporal_connect_retry", attempt=i, error=str(e)[:100])
            await asyncio.sleep(3)
    else:
        raise SystemExit("temporal unavailable")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    worker = Worker(client, task_queue=s.task_queue, workflows=[ScanWorkflow, GraphBuildWorkflow, DriftWorkflow],
                    activities=activities.ALL, max_concurrent_activities=8)
    log.info("worker_started", task_queue=s.task_queue)
    async with worker:
        await asyncio.gather(run_relay(client, stop), reconcile_loop(stop), heartbeat(stop), stop.wait())
    log.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
