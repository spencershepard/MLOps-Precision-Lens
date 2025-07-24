import os
# os.environ["PREFECT_API_URL"] = "http://prefect.local:30080/api"

from prefect.client import get_client
from prefect_kubernetes import KubernetesClusterConfig
from prefect.client.schemas.actions import WorkPoolUpdate
import asyncio

cluster_config = KubernetesClusterConfig.load("my-cluster")
block_document_id = cluster_config._block_document_id

async def update_work_pool(pool_name):
    async with get_client() as client:
        work_pool = await client.read_work_pool(pool_name)

        # use a json file if we need to do anything more complex. Prefect has a from_file method
        work_pool.base_job_template["variables"]["properties"]["cluster_config"] = {
            'anyOf': [{'$ref': '#/definitions/KubernetesClusterConfig'}, {'type': 'null'}],
            'default': {"$ref": {"block_document_id": block_document_id}},
            'description': 'The Kubernetes cluster config to use for job creation.'
        }
        wp_json = work_pool.model_dump_json()
        print(f"Work Pool JSON: {wp_json}")
        update = WorkPoolUpdate(
            base_job_template=work_pool.base_job_template
        )
        await client.update_work_pool(pool_name, update)

asyncio.run(update_work_pool("my-pool"))