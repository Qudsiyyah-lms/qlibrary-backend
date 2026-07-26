from rest_framework import serializers

from .models import Book, Subject


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "name", "slug"]


class BookListSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    cover_url = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = [
            "id",
            "slug",
            "title",
            "author",
            "subject",
            "cover_url",
            "file_size_bytes",
            "download_count",
        ]

    def get_cover_url(self, obj):
        if not obj.cover_image:
            return None
        return obj.cover_image.url


class BookDetailSerializer(BookListSerializer):
    class Meta(BookListSerializer.Meta):
        fields = BookListSerializer.Meta.fields + [
            "description",
            "language",
            "publication_year",
            "created_at",
        ]


class AdminBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = [
            "id",
            "slug",
            "title",
            "author",
            "subject",
            "description",
            "language",
            "publication_year",
            "pdf_file",
            "cover_image",
            "file_size_bytes",
            "download_count",
            "is_published",
            "uploaded_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "file_size_bytes",
            "download_count",
            "uploaded_by",
            "created_at",
            "updated_at",
        ]
