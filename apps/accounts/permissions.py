from rest_framework.permissions import BasePermission


class IsActiveStaff(BasePermission):
    """Admin biasa: boleh kelola kitab/subject, tidak boleh kelola akun admin lain."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_staff)


class IsActiveSuperUser(BasePermission):
    """Superuser: boleh mengundang/menonaktifkan akun admin lain (pewarisan admin)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_superuser)
