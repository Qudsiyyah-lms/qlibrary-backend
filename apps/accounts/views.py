from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import AdminInvite, LoginOTP
from .serializers import (
    AcceptInviteSerializer,
    AdminUserSerializer,
    LoginSerializer,
    MeSerializer,
    ResendOTPSerializer,
    VerifyOTPSerializer,
)
from .utils import send_invite_email, send_otp_email

User = get_user_model()


class LoginThrottle(AnonRateThrottle):
    scope = "login"


class OTPThrottle(AnonRateThrottle):
    scope = "otp"


def _cookie_kwargs(max_age_seconds: int) -> dict:
    return {
        "max_age": max_age_seconds,
        "httponly": True,
        "secure": not settings.DEBUG,
        "samesite": "Lax",
    }


def _set_jwt_cookies(response: Response, user) -> None:
    refresh = RefreshToken.for_user(user)
    access = refresh.access_token

    response.set_cookie(
        settings.JWT_ACCESS_COOKIE_NAME,
        str(access),
        **_cookie_kwargs(int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())),
    )
    response.set_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        str(refresh),
        **_cookie_kwargs(int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())),
    )


class LoginView(APIView):
    """Langkah 1: verifikasi password, kirim OTP ke email admin (BACKEND_SPEC.md §6.1)."""

    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        otp, raw_code = LoginOTP.generate_for(user, settings.OTP_LIFETIME_MINUTES)
        send_otp_email(user, raw_code)

        return Response({"login_token": str(otp.id)}, status=status.HTTP_200_OK)


class VerifyOTPView(APIView):
    """Langkah 2: verifikasi kode OTP, set cookie JWT httpOnly."""

    permission_classes = [AllowAny]
    throttle_classes = [OTPThrottle]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        login_token = serializer.validated_data["login_token"]
        code = serializer.validated_data["code"]

        otp = LoginOTP.objects.filter(id=login_token).select_related("user").first()
        if otp is None or otp.is_expired():
            return Response(
                {"detail": "Sesi login kedaluwarsa, silakan login ulang."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not otp.check_code(code):
            otp.attempts += 1
            otp.save(update_fields=["attempts"])
            if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
                otp.delete()
                return Response(
                    {"detail": "Terlalu banyak percobaan salah, silakan login ulang."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response({"detail": "Kode OTP salah."}, status=status.HTTP_400_BAD_REQUEST)

        user = otp.user
        otp.delete()

        response = Response({"detail": "Login berhasil."}, status=status.HTTP_200_OK)
        _set_jwt_cookies(response, user)
        return response


class ResendOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OTPThrottle]

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        login_token = serializer.validated_data["login_token"]

        otp = LoginOTP.objects.filter(id=login_token).select_related("user").first()
        if otp is None or otp.is_expired():
            return Response(
                {"detail": "Sesi login kedaluwarsa, silakan login ulang."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cooldown_end = otp.last_sent_at + timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS)
        if timezone.now() < cooldown_end:
            wait_seconds = int((cooldown_end - timezone.now()).total_seconds())
            return Response(
                {"detail": f"Tunggu {wait_seconds} detik sebelum mengirim ulang."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        new_otp, raw_code = LoginOTP.generate_for(otp.user, settings.OTP_LIFETIME_MINUTES)
        otp.delete()
        send_otp_email(new_otp.user, raw_code)

        return Response({"login_token": str(new_otp.id)}, status=status.HTTP_200_OK)


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if raw_refresh is None:
            return Response({"detail": "Tidak ada sesi aktif."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = RefreshToken(raw_refresh)
            access = refresh.access_token
        except TokenError:
            return Response(
                {"detail": "Sesi tidak valid, silakan login ulang."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        response = Response({"detail": "Token diperbarui."}, status=status.HTTP_200_OK)
        response.set_cookie(
            settings.JWT_ACCESS_COOKIE_NAME,
            str(access),
            **_cookie_kwargs(int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())),
        )
        if settings.SIMPLE_JWT["ROTATE_REFRESH_TOKENS"]:
            response.set_cookie(
                settings.JWT_REFRESH_COOKIE_NAME,
                str(refresh),
                **_cookie_kwargs(int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())),
            )
        return response


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        response = Response({"detail": "Logout berhasil."}, status=status.HTTP_200_OK)
        response.delete_cookie(settings.JWT_ACCESS_COOKIE_NAME)
        response.delete_cookie(settings.JWT_REFRESH_COOKIE_NAME)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)


class AcceptInviteView(APIView):
    """Publik, token-gated: buat akun admin baru dari undangan (BACKEND_SPEC.md §6.2)."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AcceptInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_token = serializer.validated_data["token"]
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        invite = None
        candidates = AdminInvite.objects.filter(accepted_at__isnull=True, revoked_at__isnull=True)
        for candidate in candidates:
            if candidate.is_usable() and candidate.check_token(raw_token):
                invite = candidate
                break

        if invite is None:
            return Response(
                {"detail": "Undangan tidak valid atau sudah kedaluwarsa."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.create_user(
            username=username,
            email=invite.email,
            password=password,
            is_staff=True,
            is_superuser=invite.grant_superuser,
        )
        invite.accepted_at = timezone.now()
        invite.save(update_fields=["accepted_at"])

        return Response(AdminUserSerializer(user).data, status=status.HTTP_201_CREATED)
