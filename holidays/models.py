# holidays/models.py

from django.db import models


class Holiday(models.Model):

    name = models.CharField(max_length=200)

    date = models.DateField(unique=True)

    description = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        return self.name
