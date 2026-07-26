from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import AdminInvite

User = get_user_model()


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if user is None or not user.is_active or not user.is_staff:
            # Pesan generik — jangan bocorkan username/password mana yang salah.
            raise serializers.ValidationError("Username atau password salah.")
        attrs["user"] = user
        return attrs


class VerifyOTPSerializer(serializers.Serializer):
    login_token = serializers.UUIDField()
    code = serializers.CharField(min_length=6, max_length=6)


class ResendOTPSerializer(serializers.Serializer):
    login_token = serializers.UUIDField()


class AcceptInviteSerializer(serializers.Serializer):
    token = serializers.CharField()
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username sudah digunakan.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "is_superuser"]


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "is_active", "is_superuser", "last_login", "date_joined"]
        read_only_fields = ["id", "username", "email", "last_login", "date_joined"]


class AdminInviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    grant_superuser = serializers.BooleanField(default=False)


class AdminInviteListSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminInvite
        fields = ["id", "email", "grant_superuser", "expires_at", "created_at"]
