from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AdminInvite
from .permissions import IsActiveSuperUser
from .serializers import AdminInviteListSerializer, AdminInviteSerializer, AdminUserSerializer
from .utils import send_invite_email

User = get_user_model()


class AdminManagementViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Kelola akun admin (khusus superuser) — dipakai untuk pewarisan admin.

    Menonaktifkan/mencabut superuser dari sebuah akun ditolak kalau itu akan
    menyisakan 0 superuser aktif di sistem (lihat BACKEND_SPEC.md §6.2).
    """

    queryset = User.objects.filter(is_staff=True).order_by("username")
    serializer_class = AdminUserSerializer
    permission_classes = [IsActiveSuperUser]
    http_method_names = ["get", "patch", "post"]

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        will_deactivate = request.data.get("is_active") is False
        will_demote = request.data.get("is_superuser") is False

        if (will_deactivate or will_demote) and instance.is_superuser:
            remaining_superusers = (
                User.objects.filter(is_superuser=True, is_active=True).exclude(pk=instance.pk).count()
            )
            if remaining_superusers == 0:
                return Response(
                    {"detail": "Tidak bisa diproses — minimal harus ada 1 superuser aktif tersisa."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return super().partial_update(request, *args, **kwargs)

    @action(detail=False, methods=["post"])
    def invite(self, request):
        serializer = AdminInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invite, raw_token = AdminInvite.generate_for(
            email=serializer.validated_data["email"],
            invited_by=request.user,
            grant_superuser=serializer.validated_data["grant_superuser"],
            lifetime_days=settings.ADMIN_INVITE_LIFETIME_DAYS,
        )
        send_invite_email(invite, raw_token, f"{settings.FRONTEND_BASE_URL}/admin/accept-invite")

        return Response({"detail": "Undangan terkirim."}, status=status.HTTP_201_CREATED)


class AdminInviteViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """List undangan admin yang masih pending + kirim ulang (khusus superuser)."""

    queryset = AdminInvite.objects.filter(accepted_at__isnull=True, revoked_at__isnull=True).order_by(
        "-created_at"
    )
    serializer_class = AdminInviteListSerializer
    permission_classes = [IsActiveSuperUser]

    @action(detail=True, methods=["post"])
    def resend(self, request, pk=None):
        invite = self.get_object()
        if not invite.is_usable():
            return Response({"detail": "Undangan sudah tidak berlaku."}, status=status.HTTP_400_BAD_REQUEST)

        new_invite, raw_token = AdminInvite.generate_for(
            email=invite.email,
            invited_by=invite.invited_by,
            grant_superuser=invite.grant_superuser,
            lifetime_days=settings.ADMIN_INVITE_LIFETIME_DAYS,
        )
        invite.revoked_at = timezone.now()
        invite.save(update_fields=["revoked_at"])
        send_invite_email(new_invite, raw_token, f"{settings.FRONTEND_BASE_URL}/admin/accept-invite")

        return Response({"detail": "Undangan dikirim ulang."}, status=status.HTTP_200_OK)
