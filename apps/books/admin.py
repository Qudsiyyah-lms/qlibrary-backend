from django.contrib import admin

from .models import Book, Subject


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "subject", "is_published", "download_count", "created_at"]
    list_filter = ["subject", "is_published", "language"]
    search_fields = ["title", "author"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ["file_size_bytes", "download_count", "created_at", "updated_at"]
