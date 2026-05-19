# SETUP.md — Cüzdan Koçu İlk Kurulum Rehberi

Bu rehber, repoyu ilk kez klonlayan birinin yerel ortamda tüm sistemi çalıştırması için yazıldı. En hızlı ve en az sürprizli yol Docker Compose kullanmaktır. Proje kuralları ve kapsam için [`docs/master_plan.md`](docs/master_plan.md), ekip çalışma akışı için [`TEAM_PROTOCOL.md`](TEAM_PROTOCOL.md) okunmalıdır.

## 1. Gereksinimler

| Araç | Gerekli sürüm | Kontrol komutu |
|---|---:|---|
| **Docker Desktop** veya **Docker Engine** | Desktop 4.30+ / Engine 27+ | `docker --version` |
| **Docker Compose** | v2 | `docker compose version` |
| **Node.js** | 22.13+ | `node --version` |
| **pnpm** | 11+ | `pnpm --version` |
| **Python** | 3.12.x, 3.13 değil | `python --version` |
| **uv** | 0.5+ | `uv --version` |
| **Git** | modern sürüm | `git --version` |
| **make** | opsiyonel | `make --version` |

Eksik araçlar için kısa notlar:

- **pnpm:** `corepack enable` ve sonra `corepack prepare pnpm@11.0.9 --activate` önerilir. Alternatif: `npm i -g pnpm`.
- **uv:** `pip install uv` veya resmi kurulum rehberi: <https://docs.astral.sh/uv/getting-started/installation/>.
- **ffmpeg:** Docker image içinde vardır. Backend'i doğrudan host üzerinde çalıştırıp `LLM_PROVIDER=gemini` ile mikrofon/STT deneyecekseniz host makinede de kurulu olmalıdır.
- **Windows'ta make:** Bazı Git Bash/WSL kurulumlarında hazır gelir, her Windows kurulumunda garanti değildir. Yoksa `choco install make` kullanın veya Makefile hedeflerinin altındaki doğrudan komutları çalıştırın.

## 2. Repoyu Klonlama ve `.env`

```bash
git clone <repo-url> btk-hackathon
cd btk-hackathon
cp .env.example .env
```

`.env` içinde en az şunları kontrol edin:

- `JWT_SECRET`: Yerel ilk çalıştırmada örnek değer çalışır; gerçek ortam için `openssl rand -hex 32` ile değiştirin.
- `NEXTAUTH_SECRET`: Yerel ilk çalıştırmada örnek değer çalışır; gerçek ortamda `JWT_SECRET`'tan farklı güçlü bir değer kullanın.
- `LLM_PROVIDER`: Doğrudan Google AI Studio için `gemini`, OpenRouter için `openrouter`.
- `GEMINI_API_KEY`: `LLM_PROVIDER=gemini` ise canlı LLM, OCR, STT/TTS ve Gemini Live özellikleri için gerekir. Anahtar: <https://aistudio.google.com/apikey>.
- `OPENROUTER_API_KEY`: `LLM_PROVIDER=openrouter` ise canlı LLM, OCR, STT/TTS özellikleri için gerekir. Anahtar: <https://openrouter.ai/keys>.
- `POSTGRES_*`, `MINIO_*`, `NEXT_PUBLIC_*` değerleri yerel Docker akışı için varsayılan halleriyle çalışır.

AI anahtarı yoksa uygulamanın temel ekranları açılır. Ancak gerçek model yanıtları, gerçek fiş OCR, sağlayıcı destekli STT/TTS ve canlı ses özellikleri sınırlı kalır veya Türkçe hazırlık hatası döner.

## 3. Docker ile İlk Çalıştırma

İlk deneme için önerilen yol budur. Backend, frontend, Postgres ve MinIO birlikte çalışır.

1. Stack'i başlatın:

```bash
docker compose up --build
```

Bu terminal açık kalsın. Migration, seed ve kontrol komutlarını ikinci terminalden çalıştırın.

Başlangıçta şunları görmelisiniz:

1. `cuzdan-postgres` healthy olur.
2. `cuzdan-minio` başlar; web konsolu <http://localhost:9001>.
3. `cuzdan-backend` build olur ve 8000 portunda uvicorn başlatır.
4. `cuzdan-frontend` build olur ve 3000 portunda servis verir.

2. Backend health kontrolü yapın:

```bash
curl http://localhost:8000/health
```

Beklenen yanıt:

```json
{"status":"ok","version":"0.1.0"}
```

3. Veritabanı migration'larını çalıştırın:

```bash
docker compose exec backend uv run alembic upgrade head
```

Migration çalışmadan login/register, demo hesap listesi ve veri okuyan endpointler ilk kurulumda çalışmaz; backend tabloları otomatik oluşturmuyor.

4. Şemayı doğrulamak isterseniz:

```bash
docker compose exec postgres psql -U cuzdan -d cuzdan -c "\dt"
```

`users`, `categories`, `transactions`, `subscriptions`, `conversations`, `messages`, `agent_memory`, `proactive_insights`, `saving_goals`, `generated_reports` ve `alembic_version` tablolarını görmelisiniz.

5. Demo verisini yükleyin:

```bash
docker compose exec backend uv run python -m app.workers.demo_seed
```

6. Uygulamayı açın:

- Frontend: <http://localhost:3000>
- Backend Swagger: <http://localhost:8000/docs>
- MinIO console: <http://localhost:9001>

MinIO yerel varsayılan girişi: `minioadmin / minioadmin`.

7. Demo hesapla giriş yapın:

```text
ayse@demo.cuzdan-kocu.app / demo123
mehmet@demo.cuzdan-kocu.app / demo123
elif@demo.cuzdan-kocu.app / demo123
deniz@demo.cuzdan-kocu.app / demo123
zeynep@demo.cuzdan-kocu.app / demo123
kerem@demo.cuzdan-kocu.app / demo123
```

8. Temel ekranları gezin:

- `/dashboard`
- `/transactions`
- `/income-expense`
- `/goals`
- `/learn`
- `/chat`
- `/family`
- `/account`

`/transactions` ekranında fiş OCR akışı vardır. Eski `/receipts` URL'i `/transactions` ekranına yönlenir. `/family` ekranında child profil oluşturma ve aktif child bağlamına geçme akışı bulunur.

9. Durdurmak için:

```bash
docker compose down
```

Veritabanı ve MinIO verisini de silmek istiyorsanız:

```bash
docker compose down -v
```

`-v` yerel Postgres ve MinIO volume'larını siler; sadece disposable yerel veri için kullanın.

## 4. Host Üzerinde Hızlı Geliştirme

Günlük geliştirmede backend ve frontend'i host üzerinde çalıştırmak daha hızlıdır. Bu modda Postgres ve MinIO Docker'da kalabilir.

### 4a. Sadece Veri Servislerini Başlatın

```bash
docker compose up -d postgres minio
```

### 4b. Backend'i Host Üzerinde Başlatın

```bash
cd backend
uv sync
DATABASE_URL=postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan \
MINIO_ENDPOINT=localhost:9000 \
uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan \
MINIO_ENDPOINT=localhost:9000 \
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Host üzerinde backend çalıştırırken `DATABASE_URL` içinde Docker servis adı `postgres` değil `localhost` kullanılmalıdır. `MINIO_ENDPOINT` de `minio:9000` değil `localhost:9000` olmalıdır. Yukarıdaki inline override'ları kullanabilir veya kendi yerel `.env` dosyanızı host moduna göre değiştirebilirsiniz.

### 4c. Frontend'i Host Üzerinde Başlatın

Başka terminalde:

```bash
cd frontend
pnpm install
pnpm dev
```

Frontend dev server save sonrası otomatik yenilenir. Browser çağrıları `NEXT_PUBLIC_API_URL` kullanır. NextAuth credential login server-side çalışır; host modunda `http://localhost:8000` kullanır, Docker Compose içinde `NEXT_PRIVATE_API_URL=http://backend:8000` verilir.

## 5. Make Komutları

Repo kökünden:

```bash
make help            # hedefleri listeler
make install         # backend uv sync + frontend pnpm install
make dev             # docker compose up --build
make backend         # host üzerinde uvicorn
make frontend        # host üzerinde next dev
make migrate         # mevcut DATABASE_URL ile alembic upgrade head
make lint            # ruff + eslint + prettier --check
make format          # backend/frontend format düzeltme
make type-check      # mypy --strict + tsc --noEmit
make test            # backend pytest
make build           # docker compose build
make down            # docker compose down
```

`make backend` ve `make migrate` host üzerinde çalışır. `.env` hâlâ Docker servis adları olan `postgres` ve `minio` değerlerini kullanıyorsa host komutları hata verebilir. Bu durumda 4b'deki inline override'ları kullanın veya migration için Docker güvenli komutu tercih edin:

```bash
docker compose exec backend uv run alembic upgrade head
```

## 6. Demo Verisi ve Proaktif Worker

Migration tamamlandıktan sonra Yılmaz demo ailesini yükleyebilirsiniz.

Docker yolu:

```bash
docker compose exec backend uv run python -m app.workers.demo_seed
```

Host yolu:

```bash
cd backend
DATABASE_URL=postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan \
MINIO_ENDPOINT=localhost:9000 \
uv run python ../seeds/demo_family.py
```

Seeder `is_demo=true` olarak Ayşe ve Mehmet parent hesaplarını, Elif/Deniz/Zeynep child demo profillerini, Kerem bireysel demo hesabını, örnek işlemleri, hedefleri, kategorileri, zarfları, tekrarlayan kayıtları ve proaktif demo verisini oluşturur veya günceller.

Proaktif insight'ları manuel yenilemek için:

Docker yolu:

```bash
docker compose exec backend uv run python -m app.workers.proactive
```

Host yolu:

```bash
cd backend
DATABASE_URL=postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan \
MINIO_ENDPOINT=localhost:9000 \
uv run python -m app.workers.proactive
```

Production'da aynı worker komutu cron/platform scheduler üzerinden çalıştırılabilir. Tek bir kullanıcı için anlık yenileme gerektiğinde authenticated session ile `POST /api/insights/refresh` kullanılabilir.

## 7. Günlük Kalite Kontrolleri

Commit veya push öncesi:

```bash
make lint && make type-check && make test
```

`make lint` format drift bulursa önce `make format` çalıştırın.

## 8. Tam Smoke Test

1. `docker compose up --build` çalıştırın.
2. `docker compose exec backend uv run alembic upgrade head` çalıştırın.
3. `docker compose exec backend uv run python -m app.workers.demo_seed` çalıştırın.
4. `curl http://localhost:8000/health` → `200 OK` ve JSON yanıtı görün.
5. <http://localhost:8000/docs> açın; auth, transactions, subscriptions, receipts, chat, family, insights, reports, STT/TTS, voice, export, memory ve goal router'ları görünmelidir.
6. <http://localhost:3000> açın; giriş yapmamış kullanıcı `/login` ekranına gider.
7. Demo hesapla giriş yapın ve authenticated shell'in açıldığını doğrulayın.
8. `/dashboard`, `/transactions`, `/income-expense`, `/goals`, `/learn`, `/chat`, `/family`, `/account` ekranlarını gezin.
9. `/transactions` üzerinde `Fiş tara` akışında 5 MB altı JPG/PNG/WEBP fiş yükleyin, OCR önizlemesini kontrol edin ve işlemi onaylayın.
10. `/family` üzerinde child profil oluşturun, child bağlamına geçin, sonra `/dashboard` ve `/chat` ekranlarında aktif child banner'ını ve child kapsamlı API çağrılarını kontrol edin.
11. `GEMINI_API_KEY` veya `OPENROUTER_API_KEY` tanımlıysa chat'e finans sorusu sorun, canlı stream'i doğrulayın, mikrofon/STT ve hoparlör/TTS akışlarını deneyin.
12. `/chat` içinde fiş görseli ekleyin ve `analyze_receipt` tool trace'inin geldiğini doğrulayın. Kalıcı işlem kaydı yine `/transactions` üzerindeki düzenle-onayla akışından yapılır.
13. Chat'te aylık koç raporu isteyin; DOCX indirme kartı oluşmalı ve indirme `/api/reports/{report_id}/download` üzerinden çalışmalıdır.
14. `/dashboard` üzerinde insight banner'ının `/api/insights` ile yüklendiğini, refresh butonunun `POST /api/insights/refresh` çağırdığını kontrol edin.
15. <http://localhost:9001> MinIO console'u açın.
16. Tema butonuyla açık/koyu mod geçişini kontrol edin.
17. Repo kökünden `make test` çalıştırın.

## 9. Sorun Giderme

### `docker compose up` port 5432 / 3000 / 8000 kullanımda diyor

Başka bir süreç aynı portu kullanıyordur. İlgili süreci durdurun veya `docker-compose.yml` içindeki host port mapping'ini değiştirin.

### Backend `postgres` host'unu çözemiyor

Backend'i host üzerinde çalıştırıyorsunuz ama `DATABASE_URL` hâlâ Docker servis adı olan `postgres` kullanıyor. Çözümler:

- Backend'i Docker içinde çalıştırın: `docker compose up backend`.
- Host modunda `DATABASE_URL=postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan` kullanın.

### Alembic `function gen_random_uuid() does not exist` hatası veriyor

`pgcrypto` extension'ı ilk migration içinde kurulmalıdır. Disposable yerel DB'de yarım kalmış manuel migration sonrası olduysa volume'ları sıfırlayıp tekrar migration çalıştırabilirsiniz:

```bash
docker compose down -v
docker compose up -d --build
docker compose exec backend uv run alembic upgrade head
```

`down -v` yerel Postgres ve MinIO verisini siler; emin değilseniz kullanmayın.

### `pnpm install` ignored builds uyarısı veriyor

pnpm 11 bazı native build script'lerini sandbox'lar. Gerekirse bir kez onaylayın:

```bash
cd frontend
pnpm approve-builds --all
```

Repo `frontend/pnpm-workspace.yaml` içinde izin verilen build paketlerini de taşır; fresh clone üzerinde çoğu durumda bu adıma gerek kalmaz.

### Windows'ta `make` yok

Git Bash/WSL deneyin veya Makefile içindeki komutları doğrudan çalıştırın.

Lint için:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && cd ../frontend && pnpm lint
```

Type-check için:

```bash
cd backend && uv run python -m mypy app && cd ../frontend && pnpm type-check
```

### Frontend build `Cannot find package '@eslint/eslintrc'` hatası veriyor

`frontend/` altında dependency kurulumu eksik kalmıştır:

```bash
cd frontend
pnpm install
```

### CRLF / LF farkları oluşuyor

Repo `.gitattributes` ile text dosyalarında LF bekler. Editörünüz satır sonlarını değiştiriyorsa LF ayarlayın ve önce sadece ne değiştiğine bakın:

```bash
git status --short
git diff --check
```

Değişikliklerin sadece line-ending gürültüsü olduğundan emin olmadan dosya silmeyin veya geri almayın.

### Browser'da hydration mismatch uyarısı görünüyor

`next-themes`, mount sonrası `<html>` üzerinde tema class'ı yönetir; root layout bu nedenle `suppressHydrationWarning` kullanır. Başka hydration uyarıları varsa `localStorage`, `Date.now()` veya browser-only API'lerin `useEffect` dışında okunmadığını kontrol edin.

## 10. Proje Akışı Notları

Numaralı görevler ve sahipler için [`TEAM_PROTOCOL.md`](TEAM_PROTOCOL.md), bağımlılık/review/handoff kuralları için [`WORKDIVISION.md`](WORKDIVISION.md) dosyasına bakın. Kurulum adımı bozulursa, bozan değişiklikle aynı PR içinde bu dosya da güncellenmelidir.
