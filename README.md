# Cüzdan Koçu

> Türk aileleri için proaktif AI finans koçu. BTK Hackathon 2026 projesi.

Cüzdan Koçu; aile bütçesi takibi, fişten otomatik işlem çıkarma, çocuklara yaşa uygun finans eğitimi, hedef/zarf yönetimi, sesli koçluk ve proaktif finansal içgörüleri tek üründe birleştirir. Amaç sadece harcama kaydetmek değil; aile içinde para konuşmalarını anlaşılır, güvenli ve öğretici hale getirmektir. Yapay zeka yalnızca bir chat penceresi olarak değil; OCR, ses, eğitim, rapor, hedef ve güvenli işlem onayı akışlarında ürünün içinde çalışır.

## İçindekiler

- [Kısa Özet](#kısa-özet)
- [Hangi Sorunu Çözüyoruz?](#hangi-sorunu-çözüyoruz)
- [Diğer Bütçe Uygulamalarından Farkımız](#diğer-bütçe-uygulamalarından-farkımız)
- [Demo Girişleri](#demo-girişleri)
- [Ekran Görüntüleri](#ekran-görüntüleri)
- [Özellikler](#özellikler)
- [Yapay Zeka ve Gemini Kullanımı](#yapay-zeka-ve-gemini-kullanımı)
- [Teknik Mimari](#teknik-mimari)
- [Gereksinimler](#gereksinimler)
- [İşletim Sistemine Göre Kurulum](#işletim-sistemine-göre-kurulum)
- [Docker ile Çalıştırma](#docker-ile-çalıştırma)
- [Host Üzerinde Geliştirme](#host-üzerinde-geliştirme)
- [Ortam Değişkenleri](#ortam-değişkenleri)
- [Doğrulama ve Test](#doğrulama-ve-test)
- [Sorun Giderme](#sorun-giderme)
- [Deploy](#deploy)

## Kısa Özet

- **Finans koçu:** Türkçe konuşan, aile bağlamını bilen, finansal danışmanlık yapmadan eğitim ve simülasyon sunan AI ajanı.
- **Fiş OCR:** Arayüzden JPG/PNG/WEBP fiş görseli yüklenir; satıcı, tarih, tutar, kategori ve kalemler çıkarılır; kullanıcı onayladıktan sonra işlem kaydedilir.
- **Aile modu:** Ebeveyn kendi ailesindeki ebeveyn/çocuk profillerinin verisini görebilir; çocuk profili sadece kendi kapsamına erişir.
- **Çocuk modu:** Yanıtlar yaşa uygun, somut örneklerle ve yargılayıcı olmayan bir dille verilir.
- **Dashboard:** Gelir/gider özeti, kategori dağılımı, zarf bütçeleri, hedefler ve proaktif uyarılar. Aile kırılımları ayrı `/family` ekranındadır.
- **Hedefler ve zarflar:** Birikim hedefi, harcama azaltma hedefi, kategori bazlı aylık zarf bütçesi ve AI destekli tasarruf planları.
- **Sesli kullanım:** Mikrofonla konuşma, yazılı yanıtı sesli dinleme, Gemini Live veya OpenRouter cascade tabanlı sesli koçluk.
- **Veri sahipliği:** Kullanıcı verisini ZIP olarak dışa aktarabilir, gerçek hesaplar silinebilir; demo hesaplar jüri/sunum için korunur.

## Hangi Sorunu Çözüyoruz?

Türkiye'de ailelerin para hayatı çoğu zaman bankacılık uygulaması, kredi kartı ekstresi, nakit fişleri, çocuk harçlığı ve aile içi konuşmalar arasında dağınık kalır. Banka uygulamaları tek hesabı iyi gösterir; ama aile bütçesini, nakit harcamayı, fişi, çocuk profilini ve finansal öğrenmeyi aynı yerde birleştirmez.

Cüzdan Koçu bu boşluğu üç parçayı bağlayarak kapatır:

- **Tek hane bütçesi:** Parent ve child profilleri aynı aile bağlamında tutulur; herkes sadece kendi yetkili veri kapsamını görür.
- **Anlatan koç:** Harcama verisi, hedefler ve abonelikler üzerinden Türkçe, yargılayıcı olmayan, eğitici açıklamalar üretir.
- **Çocuk dili:** Çocuk modunda harçlık, kumbara, dondurma, okul ve bayram parası gibi somut örneklerle finansal kavramları sadeleştirir.

## Diğer Bütçe Uygulamalarından Farkımız

| Boyut | Banka uygulamaları | Genel bütçe uygulamaları | Cüzdan Koçu |
|---|---|---|---|
| Veri kapsamı | Genellikle tek banka/kart | Kullanıcının manuel kurduğu bütçe | Banka bağımsız manuel kayıt + fiş OCR + aile bağlamı |
| Aile/çocuk | Yok veya çok sınırlı | Genellikle bireysel | Parent/child profilleri, aile kapsamı ve child güvenli görünümü |
| Eğitim | Ürün odaklı veya genel içerik | Çoğunlukla takip ve raporlama | Yaşa/seviyeye göre finans okulu ve koç açıklamaları |
| Proaktivite | Reaktif bildirimler | Grafik ve limit uyarıları | Dashboard'da kural tabanlı proaktif koç notları |
| Sesli kullanım | Çoğunlukla yok | Çoğunlukla yok | Mikrofon, TTS ve Gemini Live/OpenRouter cascade ses akışı |
| Veri sahipliği | Platforma bağlı | Değişken | ZIP export, hesap silme ve demo/gerçek veri ayrımı |
| Finansal tavsiye sınırı | Ürün satışı olabilir | Değişken | Yatırım tavsiyesi yok; eğitim ve simülasyon var |

## Demo Girişleri

Demo verisini seed ettikten sonra şu hesaplarla giriş yapılabilir:

| Kullanıcı | Rol | E-posta | Şifre |
|---|---|---|---|
| Ayşe Yılmaz | Parent | `ayse@demo.cuzdan-kocu.app` | `demo123` |
| Mehmet Yılmaz | Parent | `mehmet@demo.cuzdan-kocu.app` | `demo123` |
| Elif Yılmaz | Çocuk demo profili | `elif@demo.cuzdan-kocu.app` | `demo123` |
| Deniz Yılmaz | Çocuk demo profili | `deniz@demo.cuzdan-kocu.app` | `demo123` |
| Zeynep Yılmaz | Yetişkin çocuk demo profili | `zeynep@demo.cuzdan-kocu.app` | `demo123` |
| Kerem | Bireysel kullanıcı | `kerem@demo.cuzdan-kocu.app` | `demo123` |

Demo hesapları `is_demo=true` bayrağıyla işaretlidir; gerçek kullanıcı verisiyle karışmaz ve jüri/sunum verisini korumak için hesap silme akışıyla silinemez.

Demo seed komutu:

```bash
cd backend
uv run python ../seeds/demo_family.py
```

Docker içinde çalışırken alternatif:

```bash
docker compose exec backend uv run python -m app.workers.demo_seed
```

## Ekran Görüntüleri

### Login

Demo hesap seçici ve e-posta/şifre giriş ekranı.

![Login](docs/screenshots/login.png)

### Panel

Aylık özet, proaktif koç notu, zarf bütçeleri ve hedef rayı.

![Panel](docs/screenshots/dashboard.png)

### İşlemler

Tek seferlik işlem formu, tekrarlayan kayıt özeti ve son işlemler listesi.

![İşlemler](docs/screenshots/işlemler.png)

### Fiş Tarama

Fiş görselinden çıkan OCR adayını kullanıcı onayına sunan düzenleme penceresi.

![Fiş Tarama](docs/screenshots/fiş_tarama.png)

### Sohbet

Kullanıcının market harcaması sorusuna verilen koç yanıtı ve grafik kartı.

![Sohbet](docs/screenshots/agent_chat.png)

### Hedefler

Birikim hedefleri, harcama azaltma hedefleri, hedef oluşturma formu ve AI taktikleri.

![Hedefler](docs/screenshots/hedefler.png)

### Aile Modu

Ebeveyn görünümünde aile finans özeti, çocuk profilleri ve aktif profil yönetimi.

![Aile Modu](docs/screenshots/aile_modu.png)

### Dersler

Haftalık quiz, özel ders oluşturma formu ve seviyeye göre finans dersleri.

![Dersler](docs/screenshots/dersler.png)

## Özellikler

### 1. Kimlik Doğrulama ve Kullanıcı Profili

- E-posta/şifre ile kayıt ve giriş.
- NextAuth JWT session içinde FastAPI bearer token taşınır.
- Sistem rolleri: parent, child, individual. Kayıt ekranında parent veya individual hesap açılır; child profilleri aile ekranından ebeveyn tarafından oluşturulur.
- Finans seviyesi: beginner, intermediate, advanced, child.
- Kullanıcı profilini güncelleme, şifre değiştirme, veri dışa aktarma ve hesap silme.
- Demo hesaplar silinemez; sunum verisi korunur.

### 2. Aile ve Çocuk Profili

- Parent aile üyelerini ve çocuk profillerini yönetir.
- Parent, child profiline geçerek dashboard/chat işlemlerini çocuğun güvenli veri kapsamıyla kullanabilir.
- Child sadece kendi işlem, hedef, chat ve hafıza kayıtlarını görür.
- Parent aile özetinde aynı aile kapsamındaki ebeveyn/çocuk profillerinin kategori dağılımını ve finansal durumunu agregeli izler.

### 3. Dashboard ve Proaktif İçgörüler

- Aylık gelir, gider, net bakiye ve önceki ay karşılaştırmaları.
- Kategori bazlı harcama dağılımları.
- Zarf bütçe durumu ve hedef ilerlemesi.
- Ay sonu projeksiyonu bugüne kadarki harcama temposunu ay sonuna yansıtır.
- Aylık özet kartı, kullanıcının gelir/gider/net özetini kopyalayıp paylaşabileceği kısa metne dönüştürür.
- Karşılaştırmalı kategori bandı, seçili kategorileri yaklaşık Türk hane referanslarıyla yan yana gösterir; gerçek tüketici paneli verisi olduğunu iddia etmez.
- Proaktif koç notları: düşük aktivite, aylık durum, harcama sıçraması, kategori aşımı, yaklaşan tekrarlayan ödeme, tasarruf fırsatı, fiş aktivitesi.
- Bildirim zili, tarayıcıda tutulan okunmamış sayısı, insight kapatma ve kısa süreli geri alma akışı.

### 4. İşlem Yönetimi

- Manuel gelir/gider ekleme.
- İşlem düzenleme ve silme.
- İşlem eklerken satıcı veya gelir kaynağı yazılması istenir; böylece kayıtlar sonradan anlaşılır kalır.
- Kategori oluşturma ve sistem kategorileriyle birlikte kullanma.
- Türkçe para formatı: `1.250,50 ₺`.
- Backend tarafında para `Decimal`, veritabanında `NUMERIC(12,2)` olarak tutulur.

### 5. Fiş OCR

- `/transactions` ekranında `Fiş tara` akışı.
- Arayüzde JPG, PNG ve WEBP fiş görseli desteği.
- Maksimum dosya boyutu: 5 MB.
- Fiş MinIO'ya kaydedilir, OCR sonucu düzenlenebilir aday olarak döner.
- Kullanıcı satıcı/tarih/tutar/kategori bilgisini onayladıktan sonra işlem oluşur.
- Gerçek fiş görsellerini okumak için Gemini veya OpenRouter API anahtarı gerekir; kullanıcı arayüzü görsel yükleme üzerine kuruludur.

### 6. Tekrarlayan Gelir/Gider

- Maaş, kira geliri, abonelik, fatura gibi tekrarlayan kayıtlar.
- Haftalık, aylık, yıllık ve özel tekrar aralıkları.
- Due kayıtlar `POST /api/recurring/materialize` ile işlem satırlarına çevrilir.
- Gelir ve gider ayrımı `subscriptions.type` ile yapılır.
- Aynı abonelik ve tarih için yanlışlıkla ikinci kez işlem oluşturulması sistem tarafından engellenir.

### 7. Hedefler ve Zarf Bütçeleri

- Birikim hedefleri: hedef tutar, mevcut tutar, katkı ekleme, duraklatma, tamamlama.
- Harcama azaltma hedefleri: belirli kategoride hedeflenen düşüş.
- Zarf bütçeleri: kategori bazlı aylık gider limiti.
- Zarf silindiğinde zarf listeden kalkar; geçmiş gelir/gider kayıtları silinmez.
- Chat içinden hedef/zarf oluşturma gibi mutasyonlar onay kartı ile güvenli şekilde yapılır.
- Hedef ilerlemesi belirli eşikleri geçtiğinde kullanıcıya sıcak başarı mesajları gösterilir.

### 8. AI Chat ve Agent Tools

- `/chat` ekranında cevaplar bekletilmeden, yazıldıkça canlı şekilde akar.
- Konuşma geçmişi kalıcıdır; `/chat/history` üzerinden görüntülenir ve silinebilir.
- AI koç gerektiğinde harcama özeti çıkarır, abonelikleri listeler, hedef/zarf işlemleri hazırlar, fiş analiz eder, kavram açıklar, senaryo simüle eder, grafik ve aylık rapor oluşturur.
- Veri değiştiren işlemler kullanıcı onayı olmadan kaydedilmez; önce onay kartı gösterilir.
- Kullanıcı mesajıyla başka bir kişinin verisine erişmeye çalışsa bile veri kapsamı giriş yapan kullanıcıya göre backend tarafında belirlenir.
- Yatırım tavsiyesi verilmez; ürün, al/sat, kesin getiri yönlendirmeleri reddedilir.

### 9. Finans Okulu

- Çocuk, başlangıç, orta ve ileri seviye ders katalogları.
- Özel ders oluşturma: konu, seviye, süre, örnek türü, quiz ve görsel seçimi.
- Ders açıklamaları chat/agent üzerinden oluşturulur.
- Çocuk modunda harçlık, kumbara, dondurma, okul gibi somut örnekler kullanılır.
- Haftalık quiz kartı ve tarayıcıda tutulan ilerleme takibi bulunur.

### 10. Aylık Koç Raporu

- Chat üzerinden aylık DOCX raporu oluşturulur.
- Rapor; nakit akışı, kategori notları, zarf durumu, hedefler, tekrarlayan ödemeler, aile yorumu ve gelecek ay kontrol listesini içerir.
- DOCX dosyası MinIO `reports` bucket'ında private saklanır.
- İndirme sadece giriş yapmış doğru kullanıcıya açık, backend kontrollü indirme adresi üzerinden yapılır.
- PDF değil, şu an DOCX desteklenir.

### 11. Ses, STT, TTS ve Canlı Koçluk

- Mikrofon butonu: tarayıcı destekliyorsa konuşmayı kaydeder, `/api/stt` ile metne çevirir ve chat mesajı olarak gönderir; desteklenmezse tarayıcının konuşma algılama yedeğini kullanır.
- Hoparlör butonu: asistan yanıtını `/api/tts` ile ses dosyasına çevirip oynatır; servis hata verirse tarayıcının seslendirme yedeğine düşer.
- Kulaklık butonu: sesli koçluk oturumu başlatır.
- Gemini modunda Gemini Live realtime transport kullanılır.
- OpenRouter modunda frontend tarafında kalıcı cascade döngüsü kullanılır: dinle → STT → mevcut chat/agent → TTS → tekrar dinle.
- Tarayıcının kendi konuşma algılama/seslendirme özellikleri de yedek olarak kullanılır; böylece demo sırasında dış servis aksasa bile akış tamamen kopmaz.

### 12. Veri Dışa Aktarma ve Koç Hafızası

- ZIP export: `islemler.csv`, `abonelikler.csv`, `hedefler.csv`.
- CSV dosyaları Excel'de Türkçe karakterler için UTF-8 BOM ile üretilir.
- Koç hafızası `agent_memory` tablosunda tutulur, kullanıcı görebilir ve silebilir.
- Koç, kullanıcının izin verdiği tercih/hedef notlarını sonraki konuşmalarda hatırlayabilir.
- Kart numarası, IBAN, TCKN, API anahtarı, base64 fiş gibi hassas veriler hafızaya yazılmaz veya loglanmaz.

## Yapay Zeka ve Gemini Kullanımı

Projede AI sadece metin cevap üretmek için değil, ürünün birçok yerinde görev odaklı kullanılır.

### Kullanılan AI Alanları

| Alan | Kullanım | Provider |
|---|---|---|
| Canlı finans koçu | Kullanıcı sorularını cevaplama, doğru işlem aracını seçme, Türkçe açıklama | Gemini veya OpenRouter |
| Fiş OCR | Görsel fişten JSON aday çıkarma | Seçili multimodal chat modeli: `GEMINI_MODEL` veya `OPENROUTER_MODEL` |
| Finansal kavram açıklama | Yaşa/seviyeye göre eğitim içeriği | Gemini veya OpenRouter |
| Senaryo simülasyonu | Borç/asgari ödeme/birikim gibi eğitsel senaryolar | Hesaplama aracı + AI açıklaması |
| Konsept görseli | Güvenli finans eğitimi illüstrasyonu | Gemini image veya OpenRouter image model |
| STT | Mikrofon sesini metne çevirme | Gemini audio veya OpenRouter `google/chirp-3` |
| TTS | Asistan yanıtını Türkçe seslendirme | Gemini TTS veya OpenRouter TTS |
| Gemini Live | Realtime sesli sohbet transport'u | Direct Gemini Live API |
| Aylık rapor | Veriye dayalı DOCX koç raporu | Deterministik rapor + isteğe bağlı güvenli AI görseli |

### Gemini Tarafında Kullanılan Modeller

`.env.example` içindeki varsayılanlar:

- `GEMINI_MODEL=gemini-2.5-flash`: chat/agent ve direct Gemini STT audio-understanding yolu.
- `GEMINI_IMAGE_MODEL=gemini-3.1-flash-image-preview`: konsept illüstrasyonu üretimi.
- `GEMINI_LIVE_MODEL=gemini-3.1-flash-live-preview`: kulaklık butonundaki realtime voice transport.
- `GEMINI_TTS_MODEL=gemini-3.1-flash-tts-preview`: yazılı yanıtları seslendirme.
- `GEMINI_LIVE_VOICE=Kore` ve `GEMINI_TTS_VOICE=Kore`: varsayılan ses.

OpenRouter yolu kullanıldığında varsayılan modeller:

- `OPENROUTER_MODEL=google/gemini-3.1-flash-lite`
- `OPENROUTER_IMAGE_MODEL=google/gemini-3.1-flash-image-preview`: konsept illüstrasyonu üretimi.
- `OPENROUTER_STT_MODEL=google/chirp-3`
- `OPENROUTER_TTS_MODEL=google/gemini-3.1-flash-tts-preview`

### Güvenlik ve Sınırlar

- Agent finansal danışman değildir; yatırım ürünü önermez, al/sat yönlendirmesi yapmaz.
- AI işlem araçlarında kullanıcı kimliği mesajdan alınmaz; giriş yapan kullanıcının güvenli oturum bilgisinden gelir.
- Parent, child ve individual veri sınırları tüm backend sorgularında uygulanır.
- Veri değiştiren AI işlemleri onay kartı olmadan kayıt yazmaz.
- API anahtarları, ham OCR base64'i, kart/IBAN/TCKN gibi hassas veriler loglanmamalıdır.

## Teknik Mimari

### Stack

| Katman | Teknolojiler |
|---|---|
| Frontend | Next.js 15 App Router, React 19, TypeScript, Tailwind, shadcn/ui primitives, Recharts, NextAuth |
| Backend | FastAPI, Python 3.12, SQLAlchemy 2, Alembic, Pydantic |
| Agent | LangGraph, LangChain Gemini, LangChain OpenAI-compatible OpenRouter |
| Veritabanı | PostgreSQL 16, `pgcrypto`, `NUMERIC(12,2)`, `TIMESTAMPTZ` |
| Object storage | MinIO S3-compatible buckets: receipts, illustrations, reports |
| Ses | MediaRecorder, Web Speech yedeği, Gemini Live WebSocket, sağlayıcı destekli STT/TTS |
| Paket yöneticileri | Backend `uv`, frontend `pnpm@11.0.9` |
| Deploy | Docker Compose, Coolify/Hetzner uyumlu production override |

### Servisler

- `postgres`: finansal veriler, kullanıcılar, chat geçmişi, hedefler, insight'lar.
- `minio`: fiş görselleri, AI illüstrasyonları, private DOCX raporları.
- `backend`: FastAPI API, AI koç, OCR, STT/TTS, rapor ve worker mantığı.
- `frontend`: Next.js UI, NextAuth session, chat/voice/OCR kullanıcı deneyimi.

### Ana Rotalar

| Route | Amaç |
|---|---|
| `/login` | Giriş ve demo hesap seçimi |
| `/register` | Kayıt |
| `/dashboard` | Ana finans özeti ve proaktif içgörüler |
| `/transactions` | İşlemler, tekrarlayan kayıtlar, fiş OCR |
| `/income-expense` | Gelir/gider analizleri |
| `/goals` | Hedefler ve zarf bütçeleri |
| `/learn` | Finans Okulu |
| `/chat` | AI koç sohbeti, ses, fiş eki, işlem onayları |
| `/chat/history` | Konuşma geçmişi |
| `/family` | Aile ve çocuk profili yönetimi |
| `/account` | Profil, export, hesap silme |
| `/account/memory` | Koç hafızası görüntüleme/silme |

Eski bağlantılar otomatik olarak yeni sayfalara yönlendirilir. Örnekler: `/` → `/dashboard`, `/receipts` → `/transactions`, `/dashboard/transactions` → `/transactions`, `/dashboard/income-expense` → `/income-expense`, `/dashboard/goals` → `/goals`, eski zarf/hedef derin linkleri → `/goals?...`.

### Arayüz ve Demo Detayları

- Ledger/defter temalı responsive arayüz.
- Açık tema ilk varsayılandır; kullanıcı isterse koyu temaya geçebilir.
- Sidebar, breadcrumb, bildirim zili ve aktif çocuk profili banner'ı bulunur.
- Login ekranındaki demo hesap seçici backend'deki demo hesap listesinden gelir.
- İlk kez gelen yetişkin kullanıcılar için 4 adımlı kısa ürün turu bulunur; çocuk modunda gösterilmez.
- `/income-expense` ekranında dönem filtreleri, gelir/gider çubukları, kategori dağılımı ve tekrarlayan ödeme analizi bulunur.
- `/chat/history` ekranında konuşma listesi, mesaj geçmişi, ek dosya/rapor kartları ve konuşma silme akışı vardır.
- `/learn` ekranındaki ders ilerlemesi tarayıcıda tutulur; ders içeriği chat üzerinden başlatılır.
- Çocuk modunda rozet rafı; ilk işlem, fiş tarama, pozitif bakiye, hedef ilerlemesi, kumbara katkısı ve ders başlatma gibi davranışları görünür kılar.
- `/account` ekranındaki haftalık e-posta özeti tercihi demo amaçlıdır; gerçek e-posta gönderimi uygulanmaz.

## Gereksinimler

| Araç | Gerekli sürüm | Kontrol |
|---|---:|---|
| Docker Desktop veya Docker Engine | Desktop 4.30+ / Engine 27+ | `docker --version` |
| Docker Compose | v2 | `docker compose version` |
| Node.js | 22.13+ | `node --version` |
| pnpm | 11.x | `pnpm --version` |
| Python | 3.12.x | `python --version` |
| uv | 0.5+ | `uv --version` |
| Git | modern | `git --version` |
| make | opsiyonel | `make --version` |
| ffmpeg | Backend bilgisayarınızda çalışırken Gemini STT için | `ffmpeg -version` |

Docker ile tüm sistemi çalıştırırken Python/Node bilgisayarınızda zorunlu değildir; ama geliştirme, lint, test ve Docker dışı çalıştırma için gerekir.

## İşletim Sistemine Göre Kurulum

### macOS

1. Docker Desktop for Mac kurun ve açın.
2. Gerekli araçları kurun:

```bash
brew install git python@3.12 uv node ffmpeg
corepack enable
node --version
python3.12 --version
docker compose version
```

3. pnpm sürümünü doğrulayın:

```bash
corepack prepare pnpm@11.0.9 --activate
pnpm --version
```

4. Repo'yu klonlayın ve `.env` hazırlayın:

```bash
git clone <repo-url> btk-hackathon
cd btk-hackathon
cp .env.example .env
```

### Linux

1. Docker Engine 27+ ve Compose v2 kurun.
2. Kullanıcınızı Docker grubuna eklemeniz gerekebilir:

```bash
sudo usermod -aG docker "$USER"
```

3. Terminali yeniden açın ve doğrulayın:

```bash
docker --version
docker compose version
```

4. Node, pnpm, Python 3.12, uv ve isteğe bağlı ffmpeg kurun:

```bash
node --version
corepack enable
corepack prepare pnpm@11.0.9 --activate
python3.12 --version
uv --version
ffmpeg -version
```

5. Repo'yu klonlayın:

```bash
git clone <repo-url> btk-hackathon
cd btk-hackathon
cp .env.example .env
```

### Windows

Önerilen yol WSL2 + Docker Desktop kullanmaktır.

1. Docker Desktop kurun ve WSL2 integration'ı açın.
2. Git for Windows kurun; komutları Git Bash veya WSL terminalinde çalıştırın.
3. Node 22.13+, Python 3.12 ve uv kurun.
4. pnpm'i Corepack ile aktive edin:

```bash
corepack enable
corepack prepare pnpm@11.0.9 --activate
```

5. `make` yoksa Git Bash/WSL kullanın veya Makefile komutlarının altındaki direkt komutları çalıştırın.
6. CRLF/LF sorunlarını önlemek için repoyu WSL dosya sistemi içinde tutmak daha stabil olur.
7. Repo'yu klonlayın:

```bash
git clone <repo-url> btk-hackathon
cd btk-hackathon
cp .env.example .env
```

## Docker ile Çalıştırma

İlk deneme için en güvenilir yol tüm servisleri Docker Compose ile başlatmaktır.

1. `.env` dosyasını oluşturun:

```bash
cp .env.example .env
```

2. `.env` içinde en az şu alanları kontrol edin:

- `JWT_SECRET` ve `NEXTAUTH_SECRET`: yerel demo için varsayılan değerler çalışır, gerçek ortamda `openssl rand -hex 32` ile değiştirin.
- `LLM_PROVIDER`: `gemini` veya `openrouter`.
- `GEMINI_API_KEY` veya `OPENROUTER_API_KEY`: gerçek AI/OCR/ses özellikleri için gerekir.

3. Stack'i başlatın:

```bash
docker compose up --build
```

Arka planda başlatmak için:

```bash
docker compose up -d --build
```

4. Migration çalıştırın:

```bash
docker compose exec backend uv run alembic upgrade head
```

5. Demo verisini yükleyin:

```bash
docker compose exec backend uv run python -m app.workers.demo_seed
```

6. Servisleri kontrol edin:

```bash
curl http://localhost:8000/health
```

Beklenen yanıt:

```json
{"status":"ok","version":"0.1.0"}
```

7. Uygulamayı açın:

- Frontend: <http://localhost:3000>
- Backend health: <http://localhost:8000/health>
- Backend Swagger: <http://localhost:8000/docs>
- MinIO console: <http://localhost:9001>

Lokal MinIO varsayılanı: `minioadmin / minioadmin`.

8. Durdurmak için:

```bash
docker compose down
```

Veritabanı ve MinIO volume'larını da silmek için:

```bash
docker compose down -v
```

## Host Üzerinde Geliştirme

Günlük geliştirmede backend/frontend'i host üzerinde çalıştırmak daha hızlıdır. Bu modda Postgres ve MinIO Docker'da kalabilir.

1. Sadece veri servislerini başlatın:

```bash
docker compose up -d postgres minio
```

2. Backend'i başlatın:

```bash
cd backend
uv sync
DATABASE_URL=postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan MINIO_ENDPOINT=localhost:9000 uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. Başka terminalde frontend'i başlatın:

```bash
cd frontend
pnpm install
pnpm dev
```

4. Tarayıcıdan açın:

```text
http://localhost:3000
```

Docker ağı içinde backend `postgres` ve `minio` servis adlarına bağlanır. Host üzerinde çalışırken `DATABASE_URL` için `localhost`, MinIO için `MINIO_ENDPOINT=localhost:9000` kullanılmalıdır.

## Make Komutları

Repo kökünden:

```bash
make help
make install
make dev
make migrate
make lint
make format
make type-check
make test
make build
make down
```

Compose dev container'ı `backend/tests` klasörünü mount etmez. Testleri en güvenilir şekilde host üzerinde `cd backend && uv run pytest -q` ile çalıştırın.

## Ortam Değişkenleri

Temel örnekler `.env.example` içindedir; Docker Compose bazı değerler için ayrıca güvenli yerel varsayılan sağlar. Gerçek `.env` dosyası commitlenmemelidir.

### Temel Backend

- `APP_ENV`: `development`, `production`, `test`.
- `APP_DEBUG`: debug docs/log davranışı.
- `APP_CORS_ORIGINS`: frontend origin listesi. Lokal varsayılan `http://localhost:3000`.
- `DATABASE_URL`: SQLAlchemy Postgres bağlantısı.
- `JWT_SECRET`: FastAPI bearer token secret.

### Frontend/Auth

- `NEXT_PUBLIC_API_URL`: tarayıcının backend'e eriştiği adres. Yerel: `http://localhost:8000`.
- `NEXT_PRIVATE_API_URL`: NextAuth server-side backend URL. Docker Compose frontend servisi bunu varsayılan olarak `http://backend:8000` verir; host modunda gerekirse `.env` içine eklenebilir.
- `NEXTAUTH_URL`: frontend public URL.
- `NEXTAUTH_SECRET`: NextAuth secret.

### MinIO

- `MINIO_ENDPOINT`: Docker içinde `minio:9000`; backend host üzerinde çalışıyorsa `localhost:9000`.
- `MINIO_PUBLIC_ENDPOINT`: tarayıcıya dönen MinIO object URL'leri için public base adresi. Yerel: `http://localhost:9000`; rapor dosyaları yine backend indirme endpoint'i üzerinden gelir.
- `MINIO_BUCKET_RECEIPTS`: fiş dosyaları.
- `MINIO_BUCKET_ILLUSTRATIONS`: AI eğitim görselleri.
- `MINIO_BUCKET_REPORTS`: private DOCX raporları.

### AI Sağlayıcıları

- `LLM_PROVIDER=gemini`: doğrudan Google AI Studio/Gemini yolu.
- `GEMINI_API_KEY`: chat, OCR, image, STT/TTS ve Gemini Live için anahtar.
- `LLM_PROVIDER=openrouter`: OpenRouter OpenAI-compatible yolu.
- `OPENROUTER_API_KEY`: OpenRouter chat/image/STT/TTS için anahtar.
- `ILLUSTRATION_DAILY_LIMIT`: kullanıcı başına günlük AI görsel limiti.

AI sağlayıcı anahtarı yoksa bazı chat akışları kurallı/yerel yanıtlarla sınırlı kalır; gerçek model yanıtları, görsel OCR, AI görseller, STT/TTS ve canlı ses özellikleri için Gemini veya OpenRouter anahtarı gerekir.

## Doğrulama ve Test

### Manuel Smoke Test

1. `docker compose up -d --build`
2. `docker compose exec backend uv run alembic upgrade head`
3. `docker compose exec backend uv run python -m app.workers.demo_seed`
4. `curl http://localhost:8000/health` → `200 OK`
5. <http://localhost:3000/login> açın.
6. `ayse@demo.cuzdan-kocu.app / demo123` ile giriş yapın.
7. `/dashboard` üzerinde gelir/gider ve koç notunu kontrol edin.
8. `/transactions` üzerinde manuel işlem ve `Fiş tara` akışını deneyin.
9. `/chat` üzerinde `Bu ay markete ne kadar harcadık?` diye sorun.
10. `/goals` üzerinde hedef ve zarf ekranlarını kontrol edin.
11. `/family` üzerinde child profile switch akışını kontrol edin.
12. `/account` üzerinde ZIP export butonunu kontrol edin.

### Otomatik Kontroller

Backend:

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run python -m mypy app
uv run pytest -q
```

Frontend:

```bash
cd frontend
pnpm lint
pnpm type-check
pnpm format:check
pnpm build
```

Kökten Makefile ile:

```bash
make lint
make type-check
make test
```

## Sorun Giderme

### `Sunucuya ulaşılamadı` Toast'u

Bu frontend'in backend'e HTTP response alamadığı anlamına gelir. Kontrol edin:

```bash
docker compose ps
curl http://localhost:8000/health
```

Tarayıcı adresi `http://localhost:3000` olmalıdır. Backend CORS varsayılanı `http://localhost:3000`; `http://127.0.0.1:3000` veya LAN IP ile açarsanız `.env` içinde `APP_CORS_ORIGINS` güncellemeniz gerekir.

### Container Name Conflict

Docker Compose recreate sırasında aynı isimli container kalmış olabilir. Önce durum bakın:

```bash
docker compose ps -a
docker ps -a --filter name=cuzdan-backend
```

Genelde `docker compose down` ve sonra `docker compose up -d --build` yeterlidir. Veri silmek istemiyorsanız `-v` kullanmayın.

### Port Kullanımda

Kullanılan portlar:

- `3000`: frontend
- `8000`: backend
- `5432`: Postgres
- `9000`: MinIO API
- `9001`: MinIO console

Çakışan servisi durdurun veya `docker-compose.yml` içinde host portlarını değiştirin.

### Backend `postgres` Host'unu Çözemiyor

Backend host üzerinde çalışırken `.env` hâlâ Docker servis adı olan `postgres` kullanıyordur. Host modunda şu URL'yi kullanın:

```bash
DATABASE_URL=postgresql+psycopg://cuzdan:cuzdan@localhost:5432/cuzdan
```

### pnpm Ignored Builds

pnpm 11 bazı native build script'lerini sandbox'lar. Gerekirse:

```bash
cd frontend
pnpm approve-builds --all
```

### Windows'ta `make` Yok

Git Bash veya WSL kullanın. Alternatif olarak `Makefile` içindeki komutları tek tek çalıştırın.

### Gemini STT Host Modunda WebM Kabul Etmiyor

Direct Gemini STT için host üzerinde `ffmpeg` kurulu olmalıdır. Docker image içinde bulunur.

## Deploy

Detaylı deploy runbook: [`docs/deploy.md`](docs/deploy.md).

Production Compose özeti:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm demo-seed
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm proactive-worker
```

Production ortamında en az şu değerler gerçek olmalıdır:

- `APP_ENV=production`
- `APP_DEBUG=false`
- `APP_CORS_ORIGINS=https://<frontend-domain>`
- `NEXT_PUBLIC_API_URL=https://<backend-domain>`
- `NEXT_PRIVATE_API_URL=https://<backend-domain>`
- `NEXTAUTH_URL=https://<frontend-domain>`
- güçlü `JWT_SECRET` ve `NEXTAUTH_SECRET`
- gerçek `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- gerçek `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_PUBLIC_ENDPOINT`, `MINIO_BUCKET_ILLUSTRATIONS`
- `GEMINI_API_KEY` veya `OPENROUTER_API_KEY`
- demo seed çalıştırılacaksa `DEMO_PARENT_PASSWORD`

## Proje Dokümanları

- Ana plan ve ürün kuralları: [`docs/master_plan.md`](docs/master_plan.md)
- Operasyonel karar günlüğü: [`docs/decisions.md`](docs/decisions.md)
- İlk kurulum rehberi: [`SETUP.md`](SETUP.md)
- Deploy rehberi: [`docs/deploy.md`](docs/deploy.md)
- Manuel test notları: [`docs/manual_test_added_features.md`](docs/manual_test_added_features.md)

## Lisans

MIT — [`LICENSE`](LICENSE).
