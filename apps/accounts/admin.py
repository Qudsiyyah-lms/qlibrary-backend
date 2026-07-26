from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import AdminInvite, LoginOTP, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ["username", "email", "is_staff", "is_superuser", "is_active"]


class ReadOnlyAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LoginOTP)
class LoginOTPAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["user", "attempts", "expires_at", "created_at"]


@admin.register(AdminInvite)
class AdminInviteAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["email", "grant_superuser", "invited_by", "expires_at", "accepted_at", "revoked_at"]
