import asyncio
from datetime import datetime, timezone, timedelta
from prefect import flow, get_run_logger
from prefect.client import get_client
from prefect.client.schemas.filters import FlowRunFilter, FlowRunFilterState 

LATE_THRESHOLD_MINUTES = 60  # Runs older than this threshold will be canceled

@flow(name="cleanup-late-prefect-runs")
async def cleanup_late_runs_flow():
    logger = get_run_logger()
    async with get_client() as client:
        # Find runs in 'Late' or 'Pending' state
        # Use correct type instantiation for FlowRunFilterState
        from prefect.client.schemas.filters import FlowRunFilterStateType
        flow_run_filter = FlowRunFilter(
            state=FlowRunFilterState(type=FlowRunFilterStateType(late=True, pending=True))
        )
        runs = await client.read_flow_runs(
            limit=200,
            sort="EXPECTED_START_TIME_ASC",
            flow_run_filter=flow_run_filter  # <-- use the filter object
        )
        now = datetime.now(timezone.utc)
        cancelled = 0
        for run in runs:
            scheduled_time = run.expected_start_time
            if scheduled_time and (now - scheduled_time) > timedelta(minutes=LATE_THRESHOLD_MINUTES):
                logger.info(f"Cancelling run {run.id} scheduled at {scheduled_time}")
                await client.cancel_flow_run(run.id)
                cancelled += 1
        logger.info(f"Cleanup complete. Cancelled {cancelled} late or stuck runs.")

if __name__ == "__main__":
    asyncio.run(cleanup_late_runs_flow())
