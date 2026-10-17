from celery import shared_task

from .models import Resource
from .services import sync_resource


@shared_task(
    ignore_result=True,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=900,
    time_limit=960,
)
def sync_hemis(resource: str = "all") -> None:
    # Reference resources precede dependants. Failures stop this chain; operator
    # requeues after remediation, preserving the failing resource's page cursor.
    resources = list(Resource) if resource == "all" else [Resource(resource)]
    for item in resources:
        sync_resource(item)
