from django.core.management.base import BaseCommand
from orders.projections.runner import ProjectorRunner
from orders.projections.order_projector import project_order_event

class Command(BaseCommand):
    help = "Догоняет проекцию OrderView из EventStore."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--max-batches", type=int, default=1000)

    def handle(self, *args, **options):
        runner = ProjectorRunner(projector_name="order_view_projector", project_func=project_order_event)
        total = runner.run_until_caught_up(
            batch_size=options["batch_size"],
            max_batches=options["max_batches"],
        )
        self.stdout.write(self.style.SUCCESS(f"OrderView: обработано событий: {total}"))
