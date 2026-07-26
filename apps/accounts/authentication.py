from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Baca access token JWT dari httpOnly cookie, bukan header Authorization.

    Dipakai supaya frontend (Next.js) tidak perlu menyentuh token secara
    langsung — mencegah pencurian token via XSS (lihat BACKEND_SPEC.md §6).
    """

    def authenticate(self, request):
        raw_token = request.COOKIES.get(settings.JWT_ACCESS_COOKIE_NAME)
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token
