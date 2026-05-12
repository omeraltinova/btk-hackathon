# Cüzdan Koçu

> Türk aileleri için proaktif AI finans koçu. BTK Hackathon 2026 projesi.

> ⚠️ **Status:** Aktif MVP geliştirmesi. Auth, işlem paneli, streaming chat ve fiş yükleme/onay akışı çalışıyor; nihai demo içerikleri Day 7'de eklenecek.

## Hızlı bakış

- **Asistan modu:** Fiş yükle, agent OCR ile kategorize etsin; "Bu ay markete ne kadar?" gibi soruları cevaplasın.
- **Koç modu:** Finansal kavram açıklama (yaşa/seviyeye göre), borç/kredi senaryoları simüle etme.
- **Aile bağlamı:** Parent ailenin tümünü, child sadece kendi verisini görür.
- **Proaktif insight:** Kullanmadığın abonelikler, ay ortası harcama artışları gibi uyarılar sen sormadan üretilir.

## Tech stack

Frontend: Next.js 15 (App Router) · Tailwind · shadcn/ui · Recharts
Backend: FastAPI · Python 3.12 · SQLAlchemy 2 · Alembic · APScheduler
Agent: LangGraph + Gemini 2.5 Flash
Storage: PostgreSQL 16 · MinIO (S3 uyumlu)
Deploy: Coolify on Hetzner VPS

Detaylı mimari ve yol haritası: [`docs/master_plan.md`](docs/master_plan.md).

## Bu repoyu çalıştırmak için

İlk kurulum adımları için: [`SETUP.md`](SETUP.md).
Ekip içi iş bölümü ve günlük plan: [`WORKDIVISION.md`](WORKDIVISION.md).

```bash
cp .env.example .env
docker compose up --build
# backend  → http://localhost:8000/health
# frontend → http://localhost:3000
```

## Lisans

MIT (Day 7'de `LICENSE` dosyası eklenecek).
