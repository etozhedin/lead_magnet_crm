from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Apply migrations and bootstrap an operator, serialized across PostgreSQL deploys."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("Deployment initialization requires PostgreSQL.")
        if "-pooler" in connection.settings_dict.get("HOST", ""):
            raise CommandError("Use the Neon direct connection URL for startup migrations, not a pooled URL.")
        # A session-level lock must remain on one connection. Neon direct URLs
        # support this; transaction-mode poolers cannot safely hold this lock.
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '60s'")
            cursor.execute("SELECT pg_advisory_lock(1749467001)")
            try:
                call_command("migrate", interactive=False, stdout=self.stdout)
                call_command("bootstrap_operator", stdout=self.stdout)
            finally:
                cursor.execute("SELECT pg_advisory_unlock(1749467001)")
