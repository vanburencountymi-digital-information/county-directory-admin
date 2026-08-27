from django.core.management.base import BaseCommand

from accounts.groups import seed_groups


class Command(BaseCommand):
    help = "Create directory_editor and permissions_admin Groups."

    def handle(self, *args, **options):
        seed_groups()
        self.stdout.write(self.style.SUCCESS("Seeded directory Groups."))
