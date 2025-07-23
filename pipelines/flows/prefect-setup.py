from prefect.client import get_client
from prefect_kubernetes import KubernetesClusterConfig
import asyncio

cluster_config = KubernetesClusterConfig.load("my-cluster")
block_document_id = cluster_config._block_document_id

async def update_work_pool(pool_name):
    async with get_client() as client:
        work_pool = await client.read_work_pool(pool_name)
        work_pool.base_job_template["job"]["block_document_id"] = block_document_id
        await client.update_work_pool(work_pool)

asyncio.run(update_work_pool("my-pool"))