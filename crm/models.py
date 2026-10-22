import uuid

from django.conf import settings
from django.db import models


class FormTemplate(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=160)
    html = models.TextField()
    fields = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Campaign(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    template = models.ForeignKey(FormTemplate, on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class DistributionLink(models.Model):
    class Channel(models.TextChoices):
        INSTAGRAM = "instagram", "Instagram"
        X = "x", "X"
        YOUTUBE = "youtube", "YouTube"
        THREADS = "threads", "Threads"

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="links")
    channel = models.CharField(max_length=16, choices=Channel.choices)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["campaign", "channel"], name="one_link_per_channel")]


class Visit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    link = models.ForeignKey(DistributionLink, on_delete=models.PROTECT, related_name="visits")
    visitor_id = models.UUIDField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class Lead(models.Model):
    # A single application per visit: retrying the same submission is idempotent.
    visit = models.OneToOneField(Visit, on_delete=models.PROTECT, related_name="lead")
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
