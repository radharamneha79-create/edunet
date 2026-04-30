from datetime import timedelta

from django.db import models
from django.utils import timezone


class PantryItem(models.Model):
    PRODUCE = 'Produce'
    DAIRY = 'Dairy'
    MEAT = 'Meat'

    CATEGORY_CHOICES = [
        (PRODUCE, 'Produce'),
        (DAIRY, 'Dairy'),
        (MEAT, 'Meat'),
    ]

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    quantity = models.PositiveIntegerField(default=0)
    purchase_date = models.DateField()
    expiration_date = models.DateField()

    class Meta:
        ordering = ['expiration_date', 'name']

    def __str__(self):
        return f"{self.name} ({self.category})"

    def get_status(self):
        today = timezone.localdate()
        if self.expiration_date < today:
            return 'Expired'
        if self.expiration_date <= today + timedelta(days=3):
            return 'Urgent'
        return 'Fresh'

    @property
    def status(self):
        return self.get_status()
