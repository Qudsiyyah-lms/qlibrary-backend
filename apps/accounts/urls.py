from django.urls import path

from .views import (
    AcceptInviteView,
    LoginView,
    LogoutView,
    MeView,
    RefreshView,
    ResendOTPView,
    VerifyOTPView,
)

urlpatterns = [
    path("login/", LoginView.as_view()),
    path("verify-otp/", VerifyOTPView.as_view()),
    path("resend-otp/", ResendOTPView.as_view()),
    path("refresh/", RefreshView.as_view()),
    path("logout/", LogoutView.as_view()),
    path("me/", MeView.as_view()),
    path("accept-invite/", AcceptInviteView.as_view()),
]
