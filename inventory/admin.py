from django.contrib import admin

from .models import PantryItem


@admin.register(PantryItem)
class PantryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity', 'purchase_date', 'expiration_date', 'status')
    search_fields = ('name', 'category')
    list_filter = ('category',)
    ordering = ('expiration_date', 'name')
