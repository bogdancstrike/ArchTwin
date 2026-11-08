"""Temporal workflows (ADR-0007): every durable job. Deterministic code only; side effects live in activities."""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=5), backoff_coefficient=2.0)


@workflow.defn
class ScanWorkflow:
    @workflow.run
    async def run(self, org_id: str, project_id: str, scan_id: str) -> dict:
        return await workflow.execute_activity("run_scan", args=[org_id, project_id, scan_id],
                                               start_to_close_timeout=timedelta(minutes=30), retry_policy=RetryPolicy(maximum_attempts=1))


@workflow.defn
class GraphBuildWorkflow:
    """Debounced per project: bursts of inventory.changed signals coalesce into one build (AT-CONTINUOUS_WATCHERS-002)."""

    def __init__(self) -> None:
        self.dirty = True

    @workflow.signal
    def touch(self) -> None:
        self.dirty = True

    @workflow.run
    async def run(self, org_id: str, project_id: str, debounce_s: float) -> dict:
        builds = 0
        last: dict = {}
        while self.dirty and builds < 20:
            self.dirty = False
            # quiet period: restart the timer while signals keep arriving
            while True:
                try:
                    await workflow.wait_condition(lambda: self.dirty, timeout=timedelta(seconds=debounce_s))
                    self.dirty = False
                except TimeoutError:
                    break
            last = await workflow.execute_activity("build_snapshot", args=[org_id, project_id],
                                                   start_to_close_timeout=timedelta(minutes=10), retry_policy=RETRY)
            builds += 1
        return {"builds": builds, **last}


@workflow.defn
class DriftWorkflow:
    @workflow.run
    async def run(self, org_id: str, project_id: str) -> dict:
        return await workflow.execute_activity("evaluate_drift", args=[org_id, project_id],
                                               start_to_close_timeout=timedelta(minutes=10), retry_policy=RETRY)
