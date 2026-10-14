"""Celery configuration; domain tasks are added in their owning modules."""

from celery import Celery

app = Celery("faol_talaba")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
