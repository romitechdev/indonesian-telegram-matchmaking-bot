# Changelog

## [Unreleased]

### Added
- `README.md` baru untuk ringkasan proyek, setup cepat, operasional harian, dan broadcast.
- `CHANGELOG.md` untuk mencatat perubahan versi berikutnya.

### Changed
- Riwayat match dashboard kini berbasis histori chat agar match lama tetap tampil.
- Relay chat mendukung foto biasa dan image document, serta proxy dashboard mengikuti content-type asli Telegram.
- Broadcast admin sudah memakai seluruh `telegram_id` numerik valid (int32 dan int64).
- Struktur `tools/` dirapikan menjadi `tools/ops` dan `tools/tests`.

### Removed
- Skrip helper sekali pakai di root project: `apply_css.py`, `apply_sidebar.py`, `update_layout.py`, `aktifkanlink.txt`.

## [2026-05-03]

### Fixed
- Broadcast ke user kini tidak lagi terpotong akibat filter `telegram_id` yang sebelumnya hanya membaca `int32`.
- Foto di chat/transcript lebih stabil untuk pesan foto dan image document.
