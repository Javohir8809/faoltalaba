from django.core.management.base import BaseCommand, CommandError

from integrations.hemis.adapters import HemisError, get_adapter
from integrations.hemis.models import Resource
from integrations.hemis.tasks import sync_hemis


class Command(BaseCommand):
    help = "Queue HEMIS sync on Celery; never contact HEMIS in this process."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--resource", choices=["all", *Resource.values], default="all")

    def handle(self, *args, **options) -> None:
        try:
            get_adapter()  # Fail before queueing if disabled or mock forbidden.
        except HemisError:
            raise CommandError("HEMIS adapter sozlanmagan.") from None
        try:
            sync_hemis.apply_async(args=[options["resource"]], retry=False)
        except Exception:
            raise CommandError("HEMIS vazifasini navbatga qo'yib bo'lmadi.") from None
        self.stdout.write("HEMIS sinxronizatsiyasi navbatga qo'yildi.")
