# QLibrary — Spesifikasi Backend (Django)

Dokumen ini adalah acuan pengerjaan backend untuk aplikasi e-library kitab-kitab salaf. Fokus utama: **hemat storage & RAM di VM**, **upload aman (admin only)**, **akses baca/download terbuka untuk guest**.

---

## 1. Ringkasan Fitur

- Guest (tanpa login) bisa: browse home, search judul/pengarang, filter subject, lihat detail buku, download PDF.
- Admin (login) bisa: upload kitab baru (PDF + metadata + cover), edit metadata, hapus kitab, kelola daftar subject.
- Tidak ada fitur user registration untuk guest — guest murni read-only, tanpa akun.
- Pencarian menunggu user selesai mengetik (debounce di frontend) lalu submit dengan Enter — backend cukup menyediakan satu endpoint search yang cepat & murah secara query.

---

## 2. Tech Stack

| Komponen | Pilihan | Alasan |
|---|---|---|
| Framework | Django 5.x + Django REST Framework | Admin panel bawaan bisa dipakai/di-extend, ORM matang |
| Database | PostgreSQL | Perlu index & (opsional) full text search yang solid; tetap ringan dibanding Elasticsearch |
| Auth | `djangorestframework-simplejwt` | Stateless JWT, cocok dipakai Next.js sebagai SPA/API client |
| Email (OTP & undangan admin) | `django-anymail` + provider HTTP API (Resend/Brevo/Mailgun free tier) | Kirim email via HTTP API, bukan SMTP — tidak perlu jalankan/rawat mail server di VM, dan email lebih kecil kemungkinan masuk spam dibanding SMTP dari IP VM biasa |
| File storage | **Object storage S3-compatible** (Cloudflare R2 atau Backblaze B2) via `django-storages` | Lihat §3 — ini kunci "irit storage & memory di VM" |
| Web server | Gunicorn/Uvicorn + Nginx reverse proxy | Standar, ringan |
| Task async (opsional, Fase 2) | Django-Q2 (bukan Celery+Redis) jika perlu generate thumbnail besar | Django-Q2 tidak butuh broker terpisah (bisa pakai ORM broker), lebih hemat RAM daripada Celery+Redis |

**Yang sengaja TIDAK dipakai** (untuk menjaga VM tetap ringan):
- ❌ Elasticsearch/OpenSearch — overkill untuk search judul/author/subject; Postgres index + `pg_trgm`/`SearchVector` sudah cukup.
- ❌ Celery + Redis di Fase 1 — tidak perlu task queue kalau proses upload synchronous saja masih cepat (PDF kitab jarang butuh proses berat real-time).
- ❌ Menyimpan file PDF di disk VM — lihat §3.

---

## 3. Arsitektur Penyimpanan File (bagian paling penting)

Masalah yang dihindari: kalau semua file PDF kitab disimpan di disk VM (`MEDIA_ROOT` lokal), storage VM akan terus membengkak seiring bertambahnya koleksi, dan setiap request download yang di-proxy Django akan membebani RAM (file dibaca ke memory) serta bandwidth VM.

**Solusi: Object Storage eksternal (S3-compatible), VM hanya menyimpan database + kode.**

```mermaid
flowchart LR
    subgraph VM["VM (kecil, murah)"]
        Nginx --> Gunicorn --> Django
        Django --> Postgres[(PostgreSQL\nhanya metadata)]
    end
    Django -- "upload (stream, tidak full-buffer)" --> R2[(Object Storage\nCloudflare R2 / Backblaze B2\nsemua file PDF & cover)]
    Guest[Guest Browser] -- "1. request download" --> Django
    Django -- "2. 302 redirect ke presigned URL" --> Guest
    Guest -- "3. download langsung dari sini,\ntidak lewat VM" --> R2
```

Poin kunci:
1. **PDF & cover image disimpan di object storage**, bukan di disk VM. Rekomendasi: **Cloudflare R2** (gratis 10GB, tanpa biaya egress — penting karena download PDF = banyak egress) atau Backblaze B2 sebagai alternatif.
2. **Database (Postgres) hanya menyimpan metadata** (judul, author, subject, ukuran file, url/key ke object storage). Ini kecil dan tidak akan membengkakkan VM meski koleksi kitab bertambah banyak.
3. **Download tidak di-proxy oleh Django.** Endpoint download mengembalikan **HTTP 302 redirect ke presigned URL** (URL sementara langsung ke object storage, expired dalam beberapa menit). Efeknya: RAM & bandwidth VM tidak terpakai sama sekali saat guest mengunduh PDF — file mengalir langsung dari object storage ke browser guest.
4. **Upload di-stream, bukan di-buffer penuh ke memory.** `django-storages` + `boto3` melakukan multipart upload secara streaming ke object storage, jadi Django tidak perlu menahan seluruh file PDF di RAM.
5. Cover thumbnail (opsional) di-generate sekali saat upload (misal dari halaman pertama PDF pakai `PyMuPDF`/`fitz`, ringan & tanpa dependency eksternal seperti poppler), dikompres kecil (mis. JPEG ~200px lebar), lalu langsung diupload ke object storage juga — file sementara di VM dihapus setelah proses selesai.

Implementasi teknis:
```python
# settings.py (ringkas)
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
AWS_S3_ENDPOINT_URL = env("R2_ENDPOINT_URL")       # endpoint Cloudflare R2
AWS_ACCESS_KEY_ID = env("R2_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("R2_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = env("R2_BUCKET_NAME")
AWS_QUERYSTRING_EXPIRE = 300   # presigned URL hanya valid 5 menit
AWS_DEFAULT_ACL = None         # bucket private, akses hanya lewat presigned URL
```

---

## 4. Struktur Folder Django (rekomendasi)

```
qlibrary-backend/
├── config/                  # project settings (was "qlibrary_backend")
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── urls.py
│   └── wsgi.py / asgi.py
├── apps/
│   ├── books/               # Book, Subject, Author models + API
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py         # ViewSets (public read-only)
│   │   ├── admin_views.py   # ViewSets khusus admin (upload/edit/delete)
│   │   ├── permissions.py   # IsAdminUser custom, dsb
│   │   ├── validators.py    # validasi file PDF (magic bytes, size, dsb)
│   │   └── urls.py
│   └── accounts/            # login admin, JWT
│       ├── views.py
│       └── urls.py
├── manage.py
├── requirements/
│   ├── base.txt
│   └── prod.txt
└── docker-compose.yml
```

---

## 5. Data Model

```mermaid
erDiagram
    SUBJECT ||--o{ BOOK : categorizes
    ADMINUSER ||--o{ BOOK : uploads
    ADMINUSER ||--o{ LOGINOTP : "requests login"
    ADMINUSER ||--o{ ADMININVITE : invites
    BOOK {
        uuid id PK
        string title
        string slug
        string author
        text description
        string language "ar/id/en, default ar"
        int publication_year
        string file_key "path/key di object storage"
        string cover_key "path/key cover di object storage, nullable"
        bigint file_size_bytes
        int download_count
        boolean is_published
        datetime created_at
        datetime updated_at
    }
    SUBJECT {
        uuid id PK
        string name "Fiqh, Hadits, Aqidah, Tafsir, dst"
        string slug
    }
    ADMINUSER {
        int id PK
        string username
        string email
        boolean is_staff
        boolean is_superuser
        boolean is_active
    }
    LOGINOTP {
        uuid id PK "dipakai sebagai login_token"
        int user_id FK
        string otp_hash
        int attempts
        datetime last_sent_at
        datetime expires_at
    }
    ADMININVITE {
        uuid id PK
        string email
        string token_hash
        boolean grant_superuser
        int invited_by_id FK
        datetime expires_at
        datetime accepted_at
        datetime revoked_at
    }
```

Catatan desain:
- `author` sebagai `CharField` terindeks (bukan model terpisah) di Fase 1 — cukup untuk search judul/author, tanpa kompleksitas tambahan. Bisa dinaikkan jadi model `Author` + M2M di Fase 2 kalau butuh halaman "semua kitab karya penulis X".
- `subject` = `ForeignKey` ke `Subject` (satu kitab = satu subject utama), sesuai kebutuhan filter dropdown/chip sederhana. Kalau nanti perlu multi-subject, ubah ke `ManyToManyField`.
- Field opsional metadata Fase 2 yang bisa ditambah tanpa migrasi besar: `muhaqqiq` (editor/tahqiq), `publisher`, `volume_info` — umum untuk kitab turats.
- `file_key`/`cover_key` menyimpan **key/path di bucket**, bukan URL penuh — supaya presigned URL selalu di-generate fresh saat request (§3).
- `ADMINUSER` memakai model `User` bawaan Django (`django.contrib.auth.models.User` atau custom user model) — field `email` dibuat **wajib & unik**, karena email adalah channel utama untuk OTP 2FA dan link undangan (§6).
- `LOGINOTP` dan `ADMININVITE` adalah tabel kecil (baris dihapus/kedaluwarsa terus, tidak pernah menumpuk besar) — cukup disimpan di Postgres yang sama, tidak perlu Redis terpisah untuk OTP/session sementara.

---

## 6. Autentikasi & Otorisasi

- **Guest**: tidak ada auth sama sekali, semua endpoint publik adalah `AllowAny` + method `GET` saja.
- **Admin**: login **dua langkah** — password lalu OTP email (§6.1) — baru setelah itu JWT access (15 menit) + refresh (7 hari) di-set sebagai **httpOnly cookie**.
- Ada dua tingkat admin: `is_staff` (admin biasa, bisa upload/edit/hapus kitab) dan `is_superuser` (bisa tambahan mengelola akun admin lain — undang admin baru, nonaktifkan admin lama). Lihat §6.2 untuk pewarisan admin.
- Semua endpoint `/api/admin/*` wajib `IsAuthenticated` + `IsAdminUser` (`is_staff=True`, dan `is_active=True`); endpoint `/api/admin/admins/*` khusus tambahan wajib `is_superuser=True`.
- Rate limit endpoint `login`, `verify-otp`, `resend-otp` (mis. `django-ratelimit`, per IP **dan** per akun) untuk mencegah brute force password maupun brute force kode OTP.

### 6.1 Login dengan 2FA Email

Alasan pakai OTP email (bukan authenticator app/TOTP): admin di aplikasi ini kemungkinan besar cuma 1–2 orang dan berganti dari waktu ke waktu (§6.2) — OTP email tidak butuh setup app tambahan di HP admin baru, cukup akses ke inbox email yang sudah didaftarkan.

```mermaid
sequenceDiagram
    participant Admin
    participant FE as Next.js
    participant BE as Django
    participant Email as Email Provider

    Admin->>FE: submit username + password
    FE->>BE: POST /api/auth/login/
    BE->>BE: verifikasi password
    BE->>BE: generate OTP 6 digit,\nsimpan HASH-nya di LoginOTP (expire 5 menit)
    BE->>Email: kirim kode OTP ke email admin
    BE-->>FE: 200 { login_token }
    FE->>Admin: tampilkan form input OTP
    Admin->>FE: submit kode OTP
    FE->>BE: POST /api/auth/verify-otp/ { login_token, code }
    BE->>BE: cek hash, expiry, & jumlah attempts
    BE-->>FE: 200 + Set-Cookie (JWT access/refresh, httpOnly)
    FE->>Admin: redirect ke dashboard admin
```

Detail keamanan:
1. **Kode OTP 6 digit**, disimpan **ter-hash** (`make_password`, sama seperti hash password Django) — bukan plaintext, sehingga isi tabel `LoginOTP` yang bocor tetap tidak berguna.
2. **Kedaluwarsa 5 menit** (`OTP_LIFETIME_MINUTES`). Setelah expired, harus login ulang dari langkah password.
3. **Maksimal 5 percobaan salah** (`OTP_MAX_ATTEMPTS`) per `login_token` — melewati batas ini, `LoginOTP` langsung diinvalidasi (dihapus/ditandai expired) dan admin harus login ulang dari awal. Ini mencegah brute force 000000–999999 pada satu sesi OTP.
4. **Resend OTP** (`POST /api/auth/resend-otp/`) punya cooldown 60 detik (`OTP_RESEND_COOLDOWN_SECONDS`) berdasarkan `last_sent_at`, supaya tidak dipakai untuk spam email/enumerasi.
5. `login_token` (id dari baris `LoginOTP`) **bukan** kredensial — dia cuma referensi opaque ke sesi OTP yang sedang berjalan, tidak bisa dipakai untuk apa pun tanpa kode OTP yang benar, dan tetap kedaluwarsa 5 menit.
6. Response `POST /api/auth/login/` **tidak boleh membocorkan** apakah username atau password yang salah (pesan generik "Username atau password salah") — mencegah user enumeration.
7. Setelah verifikasi OTP sukses, sistem **tidak** mengirim notifikasi "login baru" via email untuk Fase 1 (bisa ditambah di Fase 2 sebagai lapisan keamanan tambahan, terutama berguna untuk mendeteksi kalau ada yang mencoba login dengan kredensial yang bocor).

### 6.2 Pewarisan / Suksesi Admin

Kebutuhan: kalau admin yang sekarang berhenti mengelola perpustakaan, harus ada cara aman untuk mengalihkan akses ke admin baru **tanpa** berbagi password atau butuh akses server langsung.

Solusinya: sistem **multi-admin dengan undangan (invite) via email**, dikelola oleh `is_superuser`.

```mermaid
sequenceDiagram
    participant SU as Superuser (admin lama)
    participant FE as Next.js
    participant BE as Django
    participant Email as Email Provider
    participant NA as Admin baru

    SU->>FE: isi form undangan (email, jadikan superuser?)
    FE->>BE: POST /api/admin/admins/invite/
    BE->>BE: buat AdminInvite (token acak, hash, expire 3 hari)
    BE->>Email: kirim link undangan ke email admin baru
    NA->>FE: buka /admin/accept-invite?token=...
    NA->>FE: isi username & password baru
    FE->>BE: POST /api/auth/accept-invite/ { token, username, password }
    BE->>BE: validasi token, buat User is_staff=True (+is_superuser jika diberi)
    BE-->>FE: 200, akun admin baru aktif
    Note over SU,BE: Kapan pun admin lama berhenti kerja
    SU->>FE: nonaktifkan akun admin lama
    FE->>BE: PATCH /api/admin/admins/{id}/ { is_active: false }
    BE->>BE: cek dulu — pastikan minimal 1 superuser aktif tersisa
```

Aturan & pengamanan:
1. **Hanya `is_superuser`** yang boleh mengundang admin baru atau menonaktifkan admin lain — admin biasa (`is_staff` saja) tidak bisa mengelola akun admin lain.
2. Token undangan **acak (mis. `secrets.token_urlsafe(32)`), disimpan ter-hash**, **sekali pakai**, dan **kedaluwarsa 3 hari** (`ADMIN_INVITE_LIFETIME_DAYS`). Link undangan dikirim ke email tujuan, bukan ditampilkan di UI manapun.
3. Endpoint `accept-invite` publik (tidak butuh login — wajar, karena calon admin belum punya akun) tapi **hanya bisa dieksekusi dengan token valid milik email yang diundang** — bukan endpoint pendaftaran umum.
4. **Tidak ada hard delete akun admin.** Menonaktifkan admin lama dilakukan dengan `is_active=False` (bukan hapus baris `User`), supaya relasi `Book.uploaded_by` (riwayat siapa mengunggah kitab apa) tetap utuh untuk audit trail.
5. **Safeguard anti-lockout**: sebelum menonaktifkan/mencabut status superuser dari sebuah akun, backend wajib memastikan **minimal 1 akun `is_superuser=True` dan `is_active=True`** tetap tersisa di sistem — kalau tidak, request ditolak dengan error jelas. Ini mencegah perpustakaan "terkunci" karena admin terakhir menonaktifkan dirinya sendiri tanpa pengganti.
6. Undangan yang belum diterima bisa **dicabut** (`revoked_at`) atau **dikirim ulang** oleh superuser kapan saja sebelum kedaluwarsa.
7. Admin baru **tetap wajib setup 2FA email** seperti biasa saat login pertama kali — tidak ada jalur login yang melewati OTP, termasuk untuk akun yang baru diterima dari undangan.

---

## 7. Keamanan Upload (wajib, karena hanya admin yang boleh upload)

1. **Validasi tipe file berdasarkan magic bytes**, bukan hanya ekstensi `.pdf` (pakai `python-magic` atau cek header `%PDF-`) — mencegah file berbahaya disamarkan sebagai PDF.
2. **Batas ukuran file** (mis. maksimal 100MB per kitab) di level Django (`DATA_UPLOAD_MAX_MEMORY_SIZE`, dan validator custom) dan di Nginx (`client_max_body_size`).
3. **Sanitasi nama file** — jangan pakai nama asli dari user untuk key di object storage; generate nama unik (`uuid4` + `.pdf`) untuk mencegah path traversal / overwrite.
4. **Bucket object storage bersifat private** — tidak ada akses publik langsung ke bucket, semua akses lewat presigned URL yang di-generate backend (jadi tidak bisa di-hotlink/di-crawl sembarangan, dan expired otomatis).
5. **CSRF protection** aktif untuk endpoint yang pakai session (Django admin default), dan pastikan endpoint admin API di DRF pakai `SessionAuthentication` hanya untuk trusted origin atau full JWT tanpa cookie CSRF issue.
6. **Endpoint upload hanya menerima `multipart/form-data`** dengan validasi ketat field-by-field via DRF Serializer (title wajib, subject wajib ada di DB, dsb) — tolak field asing.
7. **HTTPS wajib** di production (redirect http→https, `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`).
8. **(Opsional, Fase 2) Virus/malware scan** sebelum file dianggap final — mis. integrasi ClamAV kalau resource VM memungkinkan; untuk Fase 1 cukup validasi tipe file yang ketat karena hanya admin (trusted) yang upload.
9. **Audit log sederhana**: catat `uploaded_by`, `created_at` di setiap Book — cukup dari field model, tidak perlu sistem logging terpisah dulu.

---

## 8. Daftar API Endpoint

### Publik (guest, tanpa auth)

| Method | Endpoint | Deskripsi |
|---|---|---|
| GET | `/api/books/` | List + search + filter + pagination. Query params: `q` (cari di title & author), `subject` (slug), `page`, `page_size` |
| GET | `/api/books/popular/` | Top N (mis. 10) buku berdasarkan `download_count` desc, untuk homepage |
| GET | `/api/books/{slug}/` | Detail satu buku (metadata + url cover presigned) |
| GET | `/api/books/{slug}/download/` | Increment `download_count`, lalu `302 redirect` ke presigned URL object storage |
| GET | `/api/subjects/` | List semua subject (untuk populate filter dropdown) |

Contoh response `GET /api/books/?q=bulughul&subject=hadits&page=1`:
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "b3f1...",
      "slug": "bulughul-maram",
      "title": "Bulughul Maram",
      "author": "Ibnu Hajar al-Asqalani",
      "subject": {"slug": "hadits", "name": "Hadits"},
      "cover_url": "https://r2.../covers/xxxx.jpg?X-Amz-...",
      "file_size_bytes": 15400000,
      "download_count": 812
    }
  ]
}
```

### Auth Admin (2FA, publik tapi berbasis token/OTP sementara — lihat §6.1)

| Method | Endpoint | Deskripsi |
|---|---|---|
| POST | `/api/auth/login/` | Langkah 1: verifikasi username+password, kirim OTP ke email, return `{login_token}` |
| POST | `/api/auth/verify-otp/` | Langkah 2: verifikasi `{login_token, code}`, set httpOnly cookie JWT |
| POST | `/api/auth/resend-otp/` | Kirim ulang OTP untuk `login_token` yang sama (cooldown 60 detik) |
| POST | `/api/auth/refresh/` | Refresh access token |
| POST | `/api/auth/logout/` | Hapus cookie |
| GET | `/api/auth/me/` | Profil admin yang sedang login (`username`, `email`, `is_superuser`) — dipakai frontend untuk kontrol tampilan UI |
| POST | `/api/auth/accept-invite/` | Publik, token-gated (§6.2): `{token, username, password}` → buat akun admin baru dari undangan |

### Admin — Kitab & Subject (butuh JWT, `is_staff=True`)

| Method | Endpoint | Deskripsi |
|---|---|---|
| GET | `/api/admin/books/` | List semua buku (termasuk unpublished), tanpa batas subject |
| POST | `/api/admin/books/` | Upload kitab baru (`multipart/form-data`: `title`, `author`, `subject`, `description`, `pdf_file`, `cover_image?`) |
| PATCH | `/api/admin/books/{id}/` | Edit metadata (tidak wajib re-upload file) |
| DELETE | `/api/admin/books/{id}/` | Hapus buku (metadata + file di object storage) |
| POST | `/api/admin/subjects/` | Tambah subject baru |
| PATCH/DELETE | `/api/admin/subjects/{id}/` | Edit/hapus subject |

### Admin — Kelola Akun Admin (butuh JWT, `is_superuser=True`, §6.2)

| Method | Endpoint | Deskripsi |
|---|---|---|
| GET | `/api/admin/admins/` | List semua akun admin (username, email, `is_active`, `is_superuser`, `last_login`) |
| POST | `/api/admin/admins/invite/` | Undang admin baru: `{email, grant_superuser}` → kirim email undangan |
| POST | `/api/admin/admins/{id}/resend-invite/` | Kirim ulang undangan yang belum diterima |
| PATCH | `/api/admin/admins/{id}/` | Update `is_active`/`is_superuser` (dipakai untuk menonaktifkan admin lama saat pewarisan) — ditolak kalau melanggar aturan "minimal 1 superuser aktif" |

---

## 9. Implementasi Search & Filter

- Index Postgres: `GinIndex` dengan `pg_trgm` di `title` dan `author` untuk pencarian substring/typo-tolerant yang cepat, atau `SearchVectorField` (Django full text search) kalau ingin ranking relevansi.
- Query `q` di-search ke `title` **atau** `author` (case-insensitive, `icontains`/`trigram_similar`).
- Filter `subject` sederhana: `WHERE subject__slug = ?`.
- Pagination pakai `PageNumberPagination` DRF bawaan (default `page_size=20`).
- Karena debounce ada di frontend (baru fetch setelah user selesai mengetik + Enter), backend tidak perlu throttle khusus untuk search — cukup rate limit umum di level Nginx/DRF throttle class (`AnonRateThrottle`) untuk jaga-jaga dari scraping otomatis.

---

## 10. Environment Variables

```
DJANGO_SECRET_KEY=
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=

DATABASE_URL=postgres://user:pass@host:5432/qlibrary

R2_ENDPOINT_URL=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=

JWT_ACCESS_TOKEN_LIFETIME_MIN=15
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

CORS_ALLOWED_ORIGINS=https://qlibrary-frontend-domain.com

# Email provider untuk OTP 2FA & undangan admin — pakai HTTP API (django-anymail),
# bukan SMTP mentah, supaya tidak perlu jalankan mail server sendiri di VM
EMAIL_PROVIDER=resend                 # atau: brevo, mailgun
RESEND_API_KEY=
DEFAULT_FROM_EMAIL=noreply@qlibrary.example.com

OTP_LIFETIME_MINUTES=5
OTP_MAX_ATTEMPTS=5
OTP_RESEND_COOLDOWN_SECONDS=60

ADMIN_INVITE_LIFETIME_DAYS=3
```

---

## 11. Deployment (VM ringan)

Karena file besar (PDF) tidak lagi disimpan lokal, kebutuhan disk VM hanya untuk: OS, kode, Postgres (metadata saja — kecil), dan swap. Spek VM 1 vCPU / 1GB RAM sudah cukup untuk Fase 1.

`docker-compose.yml` (gambaran layanan):
```yaml
services:
  web:
    build: .
    command: gunicorn config.wsgi:application --workers 2 --bind 0.0.0.0:8000
    env_file: .env
    depends_on: [db]
  db:
    image: postgres:16-alpine
    volumes: [pgdata:/var/lib/postgresql/data]
  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    depends_on: [web]
volumes:
  pgdata:
```
Tidak ada service Redis/Celery/Elasticsearch di Fase 1 — sengaja diminimalkan untuk hemat RAM.

---

## 12. Fase Pengerjaan (checklist)

- [ ] **Fase 0**: Setup project Django + DRF + Postgres + `.env` + docker-compose dasar
- [ ] **Fase 1 — Model & Admin Django bawaan**: model `Subject`, `Book`; daftarkan di Django admin untuk upload manual awal (sekaligus jadi admin panel darurat)
- [ ] **Fase 2 — Object storage**: integrasi `django-storages` + R2, migrasi upload agar file langsung ke bucket
- [ ] **Fase 3 — API publik**: endpoint list/search/filter/detail/download (presigned redirect) + `popular`
- [ ] **Fase 4 — Auth admin + 2FA**: model `LoginOTP`, integrasi email provider (`django-anymail`), endpoint login/verify-otp/resend-otp/refresh/logout/me, proteksi endpoint admin
- [ ] **Fase 5 — API admin kitab**: upload/edit/delete book & subject via API (dipakai dashboard Next.js, bukan cuma Django admin)
- [ ] **Fase 6 — Pewarisan admin**: model `AdminInvite`, endpoint invite/accept-invite/resend-invite, endpoint kelola admin (`is_active`/`is_superuser`) + safeguard minimal 1 superuser aktif
- [ ] **Fase 7 — Hardening keamanan**: validasi magic bytes, rate limiting (login, OTP, invite), HTTPS, security headers
- [ ] **Fase 8 — Deploy**: VM setup, Nginx, Gunicorn, Postgres, monitoring dasar (mis. Sentry gratis tier untuk error tracking)
