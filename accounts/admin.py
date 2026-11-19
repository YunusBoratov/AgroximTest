from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class AppUserAdmin(UserAdmin):
    list_display = ("username", "fish", "role", "telefon", "is_active")
    list_filter = ("role", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("Platforma", {"fields": ("role", "fish", "telefon", "lavozim", "pinfl", "inn", "tashkilot_nomi")}),
    )
