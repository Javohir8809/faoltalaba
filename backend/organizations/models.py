import uuid

from django.db import models


class Faculty(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    hemis_id = models.CharField(max_length=128, unique=True, null=True, blank=True)
    hemis_active = models.BooleanField(default=True)


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    faculty = models.ForeignKey(Faculty, on_delete=models.PROTECT, related_name="departments")
    name = models.CharField(max_length=200)
    hemis_id = models.CharField(max_length=128, unique=True, null=True, blank=True)
    hemis_active = models.BooleanField(default=True)


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hemis_id = models.CharField(max_length=128, unique=True)
    name = models.CharField(max_length=200)
    faculty = models.ForeignKey(Faculty, on_delete=models.PROTECT)
    hemis_active = models.BooleanField(default=True)


class Subject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hemis_id = models.CharField(max_length=128, unique=True)
    name = models.CharField(max_length=200)
    hemis_active = models.BooleanField(default=True)
