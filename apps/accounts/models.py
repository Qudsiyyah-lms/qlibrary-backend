import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.username


class LoginOTP(models.Model):
    """Sesi OTP sementara untuk langkah ke-2 login admin (lihat BACKEND_SPEC.md §6.1)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="login_otps")
    otp_hash = models.CharField(max_length=128)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def set_code(self, raw_code: str) -> None:
        self.otp_hash = make_password(raw_code)

    def check_code(self, raw_code: str) -> bool:
        return check_password(raw_code, self.otp_hash)

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @classmethod
    def generate_for(cls, user, lifetime_minutes: int):
        raw_code = f"{secrets.randbelow(1_000_000):06d}"
        otp = cls(user=user, expires_at=timezone.now() + timedelta(minutes=lifetime_minutes))
        otp.set_code(raw_code)
        otp.save()
        return otp, raw_code

    def __str__(self):
        return f"OTP untuk {self.user} (expires {self.expires_at})"


class AdminInvite(models.Model):
    """Undangan admin baru untuk pewarisan akses (lihat BACKEND_SPEC.md §6.2)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    token_hash = models.CharField(max_length=128)
    grant_superuser = models.BooleanField(default=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invites",
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def set_token(self, raw_token: str) -> None:
        self.token_hash = make_password(raw_token)

    def check_token(self, raw_token: str) -> bool:
        return check_password(raw_token, self.token_hash)

    def is_usable(self) -> bool:
        return self.accepted_at is None and self.revoked_at is None and timezone.now() < self.expires_at

    @classmethod
    def generate_for(cls, email: str, invited_by, grant_superuser: bool, lifetime_days: int):
        raw_token = secrets.token_urlsafe(32)
        invite = cls(
            email=email,
            invited_by=invited_by,
            grant_superuser=grant_superuser,
            expires_at=timezone.now() + timedelta(days=lifetime_days),
        )
        invite.set_token(raw_token)
        invite.save()
        return invite, raw_token

    def __str__(self):
        return f"Undangan untuk {self.email}"
