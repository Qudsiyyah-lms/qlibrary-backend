# QLibrary Backend

Backend Django + Django REST Framework untuk e-library kitab-kitab salaf. Guest bisa browse/cari/download PDF tanpa login; admin (dengan 2FA email) mengelola koleksi kitab. Detail arsitektur, alasan desain, dan daftar API lengkap ada di [`BACKEND_SPEC.md`](BACKEND_SPEC.md) — README ini fokus ke cara menjalankan project.

## Tech Stack

- Django 5 + Django REST Framework
- PostgreSQL (production) / SQLite (fallback otomatis untuk dev lokal jika `DATABASE_URL` tidak diisi)
- JWT via cookie httpOnly (`djangorestframework-simplejwt`) + 2FA OTP email
- Object storage S3-compatible (Cloudflare R2 / Backblaze B2) via `django-storages` — PDF & cover **tidak** disimpan di disk server
- Email transactional via `django-anymail` (default: Resend)

## Setup Awal

1. **Buat & aktifkan virtual environment**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements/dev.txt
   ```

3. **Siapkan environment variables**
   ```bash
   cp .env.example .env
   ```
   Isi minimal `DJANGO_SECRET_KEY` (generate dengan `python -c "import secrets; print(secrets.token_urlsafe(50))"`). Field lain (R2, Resend, dsb) boleh dikosongkan dulu untuk development — lihat catatan di §Batasan Tanpa Kredensial di bawah.

4. **Jalankan migrasi**
   ```bash
   python manage.py migrate
   ```

5. **Buat akun admin pertama** (superuser)
   ```bash
   python manage.py createsuperuser
   ```

6. **Jalankan development server**
   ```bash
   python manage.py runserver
   ```
   Cek `http://127.0.0.1:8000/api/health/` → harus mengembalikan `{"status": "ok"}`.

## Struktur Project

```
config/                 # settings (base/dev/prod), urls, wsgi/asgi
apps/
  accounts/              # User, LoginOTP (2FA), AdminInvite (pewarisan admin), auth JWT-cookie
  books/                 # Subject, Book, search/filter/download, validasi upload PDF
requirements/            # base.txt, dev.txt, prod.txt
manage.py
docker-compose.yml       # web (Django) + db (Postgres) untuk dev/staging
Dockerfile
```

## Environment Variables Penting

| Variabel | Wajib? | Keterangan |
|---|---|---|
| `DJANGO_SECRET_KEY` | Ya | Wajib diisi, tidak ada default |
| `DJANGO_SETTINGS_MODULE` | Tidak | Default `config.settings.dev`; set `config.settings.prod` di production |
| `DATABASE_URL` | Tidak (dev) / Ya (prod) | Kosongkan untuk fallback SQLite lokal |
| `R2_*` | Ya (untuk fitur upload/download berfungsi) | Kredensial object storage — tanpa ini upload PDF akan gagal |
| `RESEND_API_KEY` | Ya (untuk 2FA & undangan admin berfungsi) | Tanpa ini, pengiriman email OTP/undangan gagal |
| `CORS_ALLOWED_ORIGINS` | Ya | Origin frontend Next.js, mis. `http://localhost:3000` |
| `FRONTEND_BASE_URL` | Ya | Dipakai menyusun link di email undangan admin |

Daftar lengkap ada di [`.env.example`](.env.example).

## Batasan Tanpa Kredensial (dev tanpa R2/Resend)

Selama `R2_*` dan `RESEND_API_KEY` masih kosong:
- Endpoint yang menyimpan file (`POST /api/admin/books/`) akan gagal karena storage backend memang diarahkan ke S3-compatible, bukan disk lokal.
- Endpoint yang mengirim email (`/api/auth/login/`, `resend-otp`, undangan admin) akan gagal saat mengirim email.

Semua endpoint lain (list/search/filter buku, subject, auth flow di level model) sudah bisa diuji tanpa kredensial tersebut.

## Perintah yang Sering Dipakai

```bash
python manage.py makemigrations   # setelah mengubah models.py
python manage.py migrate
python manage.py createsuperuser
python manage.py test             # jalankan test suite
python manage.py shell            # shell interaktif Django
```

## Menjalankan dengan Docker

```bash
docker compose up --build
```
Menjalankan service `web` (Django + Gunicorn, `DJANGO_SETTINGS_MODULE=config.settings.prod`) dan `db` (Postgres). Migrasi & `collectstatic` otomatis dijalankan lewat `docker-entrypoint.sh` saat container start. Pastikan `.env` sudah lengkap sebelum menjalankan ini.

## Autentikasi Admin (ringkas)

Login admin dua langkah — lihat [`BACKEND_SPEC.md` §6](BACKEND_SPEC.md#6-autentikasi--otorisasi) untuk detail lengkap:
1. `POST /api/auth/login/` (username+password) → kode OTP dikirim ke email → dapat `login_token`
2. `POST /api/auth/verify-otp/` (`login_token` + kode) → cookie JWT httpOnly ter-set

Untuk mewariskan akses ke admin baru: superuser mengundang lewat `POST /api/admin/admins/invite/`, calon admin menerima lewat `POST /api/auth/accept-invite/`, admin lama dinonaktifkan lewat `PATCH /api/admin/admins/{id}/`.

## Referensi Lengkap

- [`BACKEND_SPEC.md`](BACKEND_SPEC.md) — arsitektur storage, ERD, daftar API lengkap, alasan setiap keputusan desain, dan checklist fase pengerjaan.
- [`qlibrary-frontend`](../qlibrary-frontend) — konsumen API ini (Next.js).
