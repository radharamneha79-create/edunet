import datetime
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse


class PantryItem(models.Model):
    CATEGORY_PRODUCE = "Produce"
    CATEGORY_DAIRY = "Dairy"
    CATEGORY_MEAT = "Meat"
    CATEGORY_PANTRY = "Pantry"
    CATEGORY_FROZEN = "Frozen"
    CATEGORY_SNACKS = "Snacks"

    CATEGORY_CHOICES = [
        (CATEGORY_PRODUCE, "Produce"),
        (CATEGORY_DAIRY, "Dairy"),
        (CATEGORY_MEAT, "Meat"),
        (CATEGORY_PANTRY, "Pantry"),
        (CATEGORY_FROZEN, "Frozen"),
        (CATEGORY_SNACKS, "Snacks"),
    ]

    UNIT_GRAMS = "g"
    UNIT_KILOGRAMS = "kg"
    UNIT_OUNCES = "oz"
    UNIT_COUNT = "count"

    UNIT_CHOICES = [
        (UNIT_GRAMS, "g"),
        (UNIT_KILOGRAMS, "kg"),
        (UNIT_OUNCES, "oz"),
        (UNIT_COUNT, "count"),
    ]

    DEFAULT_SHELF_LIFE_DAYS = {
        "produce": 7,
        "dairy": 10,
        "meat": 5,
        "pantry": 30,
        "frozen": 90,
        "snacks": 20,
        "leafy greens": 5,
        "eggs": 21,
        "bread": 5,
        "milk": 10,
        "chicken": 5,
        "beef": 5,
        "rice": 365,
        "chips": 30,
        "cookies": 30,
        "nuts": 60,
    }

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default=UNIT_COUNT)
    date_added = models.DateField(default=date.today)
    expiration_date = models.DateField(blank=True, null=True)
    expiration_time = models.TimeField(blank=True, null=True)
    image = models.ImageField(upload_to="pantry_images/", blank=True, null=True)
    qr_code_data = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ["expiration_date", "name"]

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"

    @property
    def expiration_datetime(self):
        if not self.expiration_date:
            return None
        expiration_time = self.expiration_time or datetime.time(23, 59, 59)
        return datetime.datetime.combine(self.expiration_date, expiration_time)

    @property
    def days_until_expiration(self) -> int:
        exp_dt = self.expiration_datetime
        if not exp_dt:
            return 0
        return max((exp_dt.date() - date.today()).days, 0)

    @property
    def hours_until_expiration(self) -> int:
        exp_dt = self.expiration_datetime
        if not exp_dt:
            return 0
        delta = exp_dt - datetime.datetime.now()
        return int(delta.total_seconds() // 3600)

    @property
    def status(self) -> str:
        hours = self.hours_until_expiration
        if hours < 0:
            return "Danger"
        if hours <= 48:
            return "Danger"
        if hours <= 120:
            return "Warning"
        return "Success"

    @property
    def status_class(self) -> str:
        return {
            "Success": "success",
            "Warning": "warning",
            "Danger": "danger",
        }.get(self.status, "secondary")

    def get_shelf_life_days(self) -> int:
        lookup = self.name.strip().lower()
        if lookup in self.DEFAULT_SHELF_LIFE_DAYS:
            return self.DEFAULT_SHELF_LIFE_DAYS[lookup]
        return self.DEFAULT_SHELF_LIFE_DAYS.get(self.category.lower(), 14)

    @property
    def expiration_progress(self) -> int:
        exp_dt = self.expiration_datetime
        if not exp_dt:
            return 0
        start_dt = datetime.datetime.combine(self.date_added or date.today(), datetime.time(0, 0, 0))
        total_seconds = max((exp_dt - start_dt).total_seconds(), 1)
        elapsed_seconds = max((datetime.datetime.now() - start_dt).total_seconds(), 0)
        return int(min(max((elapsed_seconds / total_seconds) * 100, 0), 100))

    def save(self, *args, **kwargs):
        if not self.expiration_date:
            shelf_life = self.get_shelf_life_days()
            base_date = self.date_added or date.today()
            self.expiration_date = base_date + timedelta(days=shelf_life)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("smart_pantry:dashboard")


class UserProfile(models.Model):
    GENDER_MALE = "male"
    GENDER_FEMALE = "female"
    GENDER_OTHER = "other"

    GENDER_CHOICES = [
        (GENDER_MALE, "Male"),
        (GENDER_FEMALE, "Female"),
        (GENDER_OTHER, "Other"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=150, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    country = models.CharField(max_length=50, blank=True)
    phone_number = models.CharField(max_length=20)
    profile_image = models.ImageField(upload_to="profile_images/", blank=True, null=True)

    def __str__(self):
        return f"{self.user.email} profile"
