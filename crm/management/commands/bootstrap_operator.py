import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Create an initial staff operator from environment secrets without changing existing users."

    def handle(self, *args, **options):
        username = os.getenv("BOOTSTRAP_OPERATOR_USERNAME", "")
        password = os.getenv("BOOTSTRAP_OPERATOR_PASSWORD", "")
        if not username and not password:
            return
        if not username or not password:
            raise CommandError("Provide both BOOTSTRAP_OPERATOR_USERNAME and BOOTSTRAP_OPERATOR_PASSWORD.")
        if len(username) > 150:
            raise CommandError("The bootstrap username must be at most 150 characters.")
        User = get_user_model()
        with transaction.atomic():
            existing = User.objects.filter(username=username).first()
            if existing:
                if not existing.is_active or not existing.is_staff:
                    raise CommandError("The bootstrap username already belongs to a non-operator account.")
                self.stdout.write("An active operator already exists; credentials were not changed.")
                return
            user = User(username=username, is_active=True, is_staff=True, is_superuser=False)
            try:
                user.full_clean(exclude=["password"])
                validate_password(password, user=user)
            except ValidationError:
                raise CommandError(
                    "The bootstrap username or password does not satisfy the configured validation policy."
                ) from None
            user.set_password(password)
            user.save()
        self.stdout.write(self.style.SUCCESS("Initial operator created."))
