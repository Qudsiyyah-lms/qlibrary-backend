from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.response import Response

from apps.accounts.permissions import IsActiveStaff

from .models import Book, Subject
from .serializers import AdminBookSerializer, SubjectSerializer


class AdminBookViewSet(viewsets.ModelViewSet):
    """CRUD kitab untuk admin (`is_staff=True`) — lihat BACKEND_SPEC.md §8."""

    queryset = Book.objects.all().select_related("subject")
    serializer_class = AdminBookSerializer
    permission_classes = [IsActiveStaff]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class AdminSubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsActiveStaff]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Tidak bisa menghapus subject yang masih dipakai oleh kitab."},
                status=status.HTTP_400_BAD_REQUEST,
            )
