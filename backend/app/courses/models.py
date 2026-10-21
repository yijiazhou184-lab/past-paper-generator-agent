from django.conf import settings
from django.db import models
from app.core.models import UUIDModel


class Course(UUIDModel):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    code = models.CharField(max_length=40, default="MSIN0180")
    scope_statement = models.TextField(default="All lecture content")
    scope_provenance = models.CharField(max_length=32, default="user_statement")
