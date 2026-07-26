from django.conf import settings
from django.core.mail import send_mail


def send_otp_email(user, raw_code: str) -> None:
    send_mail(
        subject="Kode Verifikasi Login QLibrary",
        message=(
            f"Kode verifikasi login Anda: {raw_code}\n\n"
            f"Kode berlaku selama {settings.OTP_LIFETIME_MINUTES} menit. "
            "Jangan bagikan kode ini kepada siapa pun."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def send_invite_email(invite, raw_token: str, accept_url: str) -> None:
    send_mail(
        subject="Undangan Menjadi Admin QLibrary",
        message=(
            "Anda diundang menjadi admin QLibrary.\n\n"
            f"Buka tautan berikut untuk membuat akun (berlaku {settings.ADMIN_INVITE_LIFETIME_DAYS} hari):\n"
            f"{accept_url}?token={raw_token}\n\n"
            "Jika Anda tidak merasa meminta undangan ini, abaikan email ini."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invite.email],
    )
