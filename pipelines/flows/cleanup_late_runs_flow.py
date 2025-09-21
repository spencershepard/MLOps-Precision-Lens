import os
from datetime import datetime, timezone, timedelta
import asyncio

FLOW_VERSION = "1.0.0"
os.environ.setdefault("PREFECT_LOGGING_LEVEL", "INFO")

local_development = not os.getenv("PREFECT_API_URL")
if local_development:
    print("Running in local development mode.")
    os.environ["PREFECT_API_URL"] = "http://prefect.local:30080/api"

# Load Prefect after setting the environment variable
from prefect import flow, task, get_run_logger
from prefect.client import get_client
from prefect.client.schemas.filters import FlowRunFilter
from prefect.client.schemas.objects import FlowRun
from prefect.states import StateType
from prefect.variables import Variable


@task
async def find_stuck_flow_runs(threshold_minutes: int = 60):
    """Find flow runs that are in Late or Pending state older than threshold."""
    logger = get_run_logger()
    
    try:
        async with get_client() as client:
            threshold_time = datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)
            
            # Find runs in Late or Pending state
            # Query for PENDING runs
            pending_filter = FlowRunFilter(
                state={"type": {"any_": [StateType.PENDING]}}
            )
            pending_runs = await client.read_flow_runs(
                flow_run_filter=pending_filter,
                limit=50
            )
            
            # Query for LATE runs  
            late_filter = FlowRunFilter(
                state={"type": {"any_": [StateType.LATE]}}
            )
            late_runs = await client.read_flow_runs(
                flow_run_filter=late_filter,
                limit=50
            )
            
            # Combine results and deduplicate by ID
            flow_runs_dict = {}
            for run in list(pending_runs) + list(late_runs):
                flow_runs_dict[run.id] = run
            flow_runs = list(flow_runs_dict.values())
            
            # Filter by age
            stuck_runs = []
            for run in flow_runs:
                if run.created and run.created < threshold_time:
                    stuck_runs.append(run)
            
            logger.info(f"Found {len(stuck_runs)} stuck flow runs older than {threshold_minutes} minutes")
            return stuck_runs
            
    except Exception as e:
        logger.error(f"Failed to query flow runs: {e}")
        return []


@task
async def cancel_flow_run(flow_run: FlowRun):
    """Cancel a single flow run and log the action."""
    logger = get_run_logger()
    
    try:
        async with get_client() as client:
            await client.cancel_flow_run(flow_run.id)
            
            age = datetime.now(timezone.utc) - flow_run.created if flow_run.created else "unknown"
            logger.info(
                f"Cancelled flow run '{flow_run.name}' (ID: {flow_run.id}) "
                f"in state '{flow_run.state_type}' - age: {age}"
            )
            return True
            
    except Exception as e:
        logger.error(
            f"Failed to cancel flow run '{flow_run.name}' (ID: {flow_run.id}): {e}"
        )
        return False


@task
async def cancel_stuck_runs(stuck_runs: list, max_concurrent: int = 5):
    """Cancel multiple flow runs with controlled concurrency."""
    logger = get_run_logger()
    
    if not stuck_runs:
        logger.info("No stuck runs to cancel")
        return {"cancelled": 0, "failed": 0}
    
    # Use semaphore to limit concurrent cancellations
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def cancel_with_semaphore(run):
        async with semaphore:
            return await cancel_flow_run(run)
    
    # Execute cancellations concurrently
    results = await asyncio.gather(
        *[cancel_with_semaphore(run) for run in stuck_runs],
        return_exceptions=True
    )
    
    # Count successful and failed cancellations
    cancelled = sum(1 for result in results if result is True)
    failed = len(results) - cancelled
    
    logger.info(f"Cleanup summary: {cancelled} runs cancelled, {failed} failed")
    return {"cancelled": cancelled, "failed": failed}


@flow(name="cleanup-late-runs-flow", log_prints=True)
async def cleanup_late_runs_flow(threshold_minutes: int = None):
    """
    Clean up stuck or late flow runs older than the specified threshold.
    
    Args:
        threshold_minutes: Age threshold in minutes for runs to be considered stuck. 
                          If None, reads from Prefect Variable 'cleanup_threshold_minutes' (default: 60)
    """
    logger = get_run_logger()
    logger.info(f"Starting cleanup flow (version {FLOW_VERSION})")
    
    # Get threshold from parameter or variable
    if threshold_minutes is None:
        try:
            threshold_minutes = int(Variable.get("cleanup_threshold_minutes", default="60"))
        except (ValueError, TypeError):
            threshold_minutes = 60
            logger.warning("Invalid cleanup_threshold_minutes variable, using default: 60")
    
    logger.info(f"Looking for runs older than {threshold_minutes} minutes in Late or Pending state")
    
    try:
        # Find stuck runs
        stuck_runs = await find_stuck_flow_runs(threshold_minutes)
        
        if not stuck_runs:
            logger.info("No stuck runs found - cleanup complete")
            return {"status": "success", "cancelled": 0, "failed": 0}
        
        # Cancel stuck runs
        summary = await cancel_stuck_runs(stuck_runs)
        
        logger.info(
            f"Cleanup completed: {summary['cancelled']} runs cancelled, "
            f"{summary['failed']} failed out of {len(stuck_runs)} total stuck runs"
        )
        
        return {
            "status": "success",
            "total_stuck": len(stuck_runs),
            **summary
        }
        
    except Exception as e:
        logger.error(f"Cleanup flow failed with unexpected error: {e}")
        return {"status": "failed", "error": str(e), "cancelled": 0, "failed": 0}


if __name__ == "__main__":
    # For local testing
    asyncio.run(cleanup_late_runs_flow())