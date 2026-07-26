from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Book, Subject
from .serializers import BookDetailSerializer, BookListSerializer, SubjectSerializer


class BookViewSet(viewsets.ReadOnlyModelViewSet):
    """Endpoint publik (guest): search, filter subject, detail, download, popular."""

    queryset = Book.objects.filter(is_published=True).select_related("subject")
    lookup_field = "slug"
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return BookDetailSerializer
        return BookListSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.query_params.get("q")
        subject_slug = self.request.query_params.get("subject")

        if q:
            queryset = queryset.filter(Q(title__icontains=q) | Q(author__icontains=q))
        if subject_slug:
            queryset = queryset.filter(subject__slug=subject_slug)

        return queryset

    @action(detail=False, methods=["get"])
    def popular(self, request):
        books = self.get_queryset().order_by("-download_count")[:10]
        serializer = BookListSerializer(books, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def download(self, request, slug=None):
        book = get_object_or_404(Book, slug=slug, is_published=True)
        Book.objects.filter(pk=book.pk).update(download_count=F("download_count") + 1)
        # Redirect ke presigned URL object storage — VM tidak proxy file sama
        # sekali (lihat BACKEND_SPEC.md §3).
        return redirect(book.pdf_file.url)


class SubjectViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"
