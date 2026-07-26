import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from .validators import validate_pdf_file


def book_pdf_upload_path(instance, filename):
    # Nama file di-generate acak (bukan nama asli) — mencegah path traversal
    # & tabrakan nama, sesuai BACKEND_SPEC.md §7.
    return f"books/pdf/{uuid.uuid4()}.pdf"


def book_cover_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    return f"books/covers/{uuid.uuid4()}.{ext}"


class Subject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Book(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300, db_index=True)
    slug = models.SlugField(max_length=320, unique=True, blank=True)
    author = models.CharField(max_length=300, db_index=True)
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="books")
    description = models.TextField(blank=True)
    language = models.CharField(max_length=10, default="ar")
    publication_year = models.PositiveIntegerField(null=True, blank=True)

    pdf_file = models.FileField(upload_to=book_pdf_upload_path, validators=[validate_pdf_file])
    cover_image = models.ImageField(upload_to=book_cover_upload_path, blank=True, null=True)
    file_size_bytes = models.BigIntegerField(default=0, editable=False)

    download_count = models.PositiveIntegerField(default=0, editable=False)
    is_published = models.BooleanField(default=True)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_books",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["author"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:300] or "kitab"
            slug = base_slug
            suffix = 1
            while Book.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                suffix += 1
                slug = f"{base_slug}-{suffix}"
            self.slug = slug
        if self.pdf_file:
            self.file_size_bytes = self.pdf_file.size
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
