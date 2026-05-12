# Cüzdan Koçu

> Türk aileleri için proaktif AI finans koçu. BTK Hackathon 2026 projesi.

> ⚠️ **Status:** Aktif MVP geliştirmesi. Auth, işlem paneli, dashboard analitiği, streaming chat, fiş yükleme/onay, aile/çocuk profili ve API-backed proaktif insight akışları çalışıyor; canlı deploy ve final demo içerikleri Day 7'de tamamlanacak.

## Hızlı bakış

- **Asistan modu:** Fiş yükle veya chat'e fiş ekle, agent OCR ile kategorize etsin; "Bu ay markete ne kadar?" gibi soruları cevaplasın.
- **Koç modu:** Finansal kavram açıklama (yaşa/seviyeye göre), borç/kredi senaryoları simüle etme.
- **Aile bağlamı:** Parent çocuk profili oluşturur, child login olmadan aile switch ile kendi güvenli kapsamına geçer.
- **Proaktif insight:** Harcama artışı, yaklaşan tekrarlayan ödeme, bütçe aşımı, düşük aktivite ve aylık durum özeti API üzerinden üretilir.

## Tech stack

Frontend: Next.js 15 (App Router) · Tailwind · shadcn/ui · Recharts
Backend: FastAPI · Python 3.12 · SQLAlchemy 2 · Alembic
Agent: LangGraph + Gemini 2.5 Flash veya OpenRouter (`google/gemini-2.5-flash`)
Storage: PostgreSQL 16 · MinIO (S3 uyumlu)
Worker: Manuel tetiklenebilir/scheduler-ready proaktif insight job
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

Demo seed sonrası giriş: `ayse@demo.cuzdan-kocu.app` / `demo123`.

## Lisans

MIT (Day 7'de `LICENSE` dosyası eklenecek).
