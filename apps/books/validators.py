import magic
from django.conf import settings
from django.core.exceptions import ValidationError


def validate_pdf_file(file):
    """Validasi ukuran & tipe file berdasarkan magic bytes, bukan cuma ekstensi.

    Lihat BACKEND_SPEC.md §7 — mencegah file berbahaya disamarkan sebagai PDF.
    """
    if file.size > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        raise ValidationError(f"Ukuran file melebihi batas maksimum {max_mb}MB.")

    header = file.read(2048)
    file.seek(0)
    mime_type = magic.from_buffer(header, mime=True)
    if mime_type != "application/pdf":
        raise ValidationError("File harus berupa PDF yang valid.")
