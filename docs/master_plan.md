# BTK Hackathon — Master Plan: Cüzdan Koçu

> **Tema:** Finans (e-ticaret modu iptal, finans odaklı)
> **Hedef:** Derece (3. ve üstü)
> **Takım:** 2 kişi, full-stack
> **Süre:** 11–19 Mayıs (8 gün; 19 Mayıs buffer)
> **Form kapanış:** 19 Mayıs 23:59
> **Asıl teslim:** Proje submission (form + canlı URL + repo + demo video)
> **Sunum:** YALNIZCA ilk 10'a kalırsak 7 dakika

---

## 0. Bu doküman hakkında

Bu doküman projenin **tek doğruluk kaynağıdır** (single source of truth). İki okuyucuya hizmet eder:

1. **Takım** — iki kişi de aynı sayfada başlasın, kararlar burada
2. **Coding agent** (Claude Code, Cursor, Windsurf, Aider vs) — kod üretirken bağlam buradan alınır

**Agent için kural:** Bir karar bu dokümana aykırı görünüyorsa kod yazma, önce dokümanı güncelle. Doküman güncellenmeden code drift yapma.

Bölüm 1–11 = **vizyon ve davranış** (agent buradan "ne yapıyoruz, neden?" öğrenir).
Bölüm 12+ = **teknik ayrıntı** (agent buradan "nasıl?" öğrenir).
Yeni başlayan biri sıralı okumalı.

**Bu dokümanın yardımcısı:** [`decisions.md`](decisions.md) — operasyonel günlük. Tool tuhaflıkları, kütüphane workaround'ları, ertelenmiş kararlar ve "şu sebepten böyle yaptık" notları buraya yazılır. Master plan = anayasa (yüksek stabilite, sürüm artar); decisions.md = günlük (append-only, kronolojik). Yeni bir agent oturduğunda her ikisini de okumalı; iş bitince operasyonel öğrenmeler decisions.md'ye eklenir. Mimari/scope değişikliği varsa bu master plan da güncellenir ve versiyon artar.

---

# BÖLÜM A — VİZYON VE DAVRANIŞ

## 1. Proje vizyonu

**Tek cümle:** Cüzdan Koçu, Türk aileleri için, hem harcamalarını yöneten hem finansal okuryazarlığı öğreten, proaktif bir AI ajanıdır.

**Daha uzun:** Türkiye'de aileler harcamalarını ya hiç takip etmiyor ya Excel'de takip ediyor; finansal okuryazarlık OECD ortalamasının altında; çocuklara para yönetimi sistematik şekilde öğretilmiyor. Cüzdan Koçu üç sorunu birden çözer:

1. Fiş yükle, agent otomatik kategorize etsin
2. Agent sen sormadan içgörü üretsin ("Netflix'i 3 aydır kullanmıyorsun")
3. Ebeveyn çocuğa finansal kavramları yaşa uygun dilde anlatsın

**Misyon:** Finansal okuryazarlığı evin içine sokmak; ailelerin para konuşmalarını sistemleştirmek.

---

## 2. Niye bu proje? Hangi problemi çözüyoruz?

**Problem 1: Aileler harcamalarından kopuk.**
Türk ailelerinin çoğu aylık bütçesini takip etmiyor; edenler Excel veya defter kullanıyor. Mobil bankacılık sadece banka hesabını gösterir; ailenin tümünü, fiş bazlı detayı, kategoriyi göstermez.

**Problem 2: Finansal okuryazarlık düşük.**
"Faiz nedir?", "Enflasyon nedir?", "Kredi kartı asgari ödemenin sonu nedir?" sorularının cevabı kişiselleştirilmiş değil. Mevcut kaynaklar ya çok teknik (BES sözlüğü) ya genel (YouTube videosu).

**Problem 3: Çocuklara para öğretmek zor.**
Ebeveyn "faiz" gibi bir kavramı 12 yaşındaki çocuğuna anlatmak istediğinde uygun bir dil bulamıyor; okul müfredatında yer almıyor.

**Mevcut çözümlerin eksiği:**
- Kişisel finans uygulamaları (Mint, YNAB, Akıllı Cüzdan) — reaktif, takip aracı, koç değil
- ChatGPT — kişisel veriye erişimi yok, hatırlamıyor
- Banka uygulamaları — tek banka, fiş yok, aile yok

**Bizim farkımız:** Proaktif + aile bağlamlı + Türkçe finansal koç + tek üründe.

---

## 3. Hedef kullanıcılar (Personalar)

### 3.1 Yılmaz ailesi (birincil persona, demo'da kullanılacak)

**Anne — Ayşe Yılmaz, 38, öğretmen**
- Aile bütçesini fiilen yöneten kişi
- Mobil bankacılık kullanıyor ama harcamalarını kategorize edemiyor
- Excel deniyor, tutamıyor
- Finansal okuryazarlık: orta (faiz, kredi biliyor; BES, ETF zayıf)
- Ana ihtiyacı: "Bu ay neye ne kadar harcadık?" + "Çocuk için biriktirebilir miyim?"

**Baba — Mehmet Yılmaz, 42, makine mühendisi**
- Büyük kalemlerden sorumlu (kira, fatura)
- Detaya inmek istemez
- Aboneliklerin çoğu onun kartından
- Ana ihtiyacı: "Bu ay nasıl gidiyoruz?" + "Aboneliklerimi gözden geçir"

**Çocuk — Elif Yılmaz, 12, 6. sınıf**
- Aylık 300 ₺ harçlık
- Telefonuna oyun ve eğlence harcıyor
- "Faiz nedir?" sorusu okulda cevaplanmamış
- Ana ihtiyacı: "Harçlığımı nasıl biriktirim?" + "Bunu anlamak istiyorum, kolayca"

### 3.2 Bireysel kullanıcı (ikincil persona)

**Kerem, 24, yeni mezun yazılım geliştirici**
- Tek yaşıyor, ilk maaşını almış
- Bütçe takibi sıfır, kredi kartı borcu artıyor
- Ana ihtiyacı: harcama görünürlüğü + faiz/borç simülasyonu

---

## 4. Ana kullanım senaryoları (User Stories)

Aşağıdaki senaryolar üretim için onaylı. Agent kod yazarken bunları "kabul kriteri" olarak kullanır.

| # | Persona | Kullanıcı yapar | Sistem yapar | Başarı |
|---|---|---|---|---|
| US-1 | Ayşe | Migros fişini fotoğraflar | Vision OCR, kategorize, dashboard güncel | Manuel girişten 10x hızlı |
| US-2 | Ayşe | "Bu ay markete ne kadar?" sorar | `get_spending(market, 30d)` → cevap | <3 sn yanıt |
| US-3 | Mehmet | Chat'i hiç açmaz, dashboard'a bakar | Proaktif banner: "Netflix'i 3 aydır kullanmıyorsun" | Kullanıcı sormadan içgörü |
| US-4 | Mehmet | "Aboneliklerimi göster" | `get_subscriptions` + kullanım skoru | Pasifler işaretli |
| US-5 | Ayşe | "12 yaşındaki kızıma faiz nedir nasıl anlatırım?" | `explain_concept(faiz, level=child)` | Yaşa uygun, somut örnekli |
| US-6 | Elif | Family switch'le kendi profiline geçer, "Harçlığımı nasıl biriktirim?" sorar | Koç modu child cevabı, 50 ₺/ay senaryosu | Çocuk dilinde, anlaşılır |
| US-7 | Mehmet | "Kredi kartının asgarisini ödesem ne olur?" | `simulate_scenario` + bakiye | Somut TL ve ay sayısı |
| US-8 | Ayşe | Manuel gelir/gider ekler | CRUD form, kategori önerisi | 30 sn'den az |
| US-9 | Ayşe | Aile sekmesinden Elif'i ekler | Davet sistemi yok — parent child yaratır | Parent → child görür, child → kendi |
| US-10 | Kerem | Tek başına kayıt olur | role=individual, aile özelliği gizli | Aile karmaşıklığı yok |

---

## 5. Tasarım prensipleri (NON-NEGOTIABLE)

Bu prensipler kodda ve UX'te taviz verilmez. Agent her kararda buraya başvurur.

**P1. Türkçe her zaman.** UI metni, agent çıktısı, hata mesajı, sistem mesajı Türkçedir. İngilizce sızıntı bug'dır.

**P2. Proaktif > reaktif.** Agent sadece soruya cevap veren değil, sormadan da içgörü üretendir. Her dashboard yüklemesinde en az bir insight olmalı (boş veriyse "Veri yüklemeye başla" onboarding insight'ı).

**P3. Aile bağlamı zorunlu.** Her veri parçası bir kullanıcıya bağlı; bir kullanıcı bir aileye bağlı olabilir. Veri sızıntısı (çocuk başkasının verisini görmesi) kabul edilemez bug'dır.

**P4. Tonu arkadaşça, otoriter değil.** "Yapmalısın" yerine "düşünebilirsin". Yargılayıcı dil yasak ("çok harcadın" yanlış; "geçen aya göre %30 artış var" doğru).

**P5. Çocuk dilinde somut örnek.** Çocuk modunda teknik terimler değil oyuncak, harçlık, dondurma, okul, doğum günü hediyesi gibi referanslar.

**P6. Veri sahipliği kullanıcıya ait.** Export butonu (CSV), silme butonu (cascade) vardır.

**P7. Agent finansal danışman değil.** Yatırım önerisi vermez. "Şunu al, sat" demez. Bilgilendirir ve simüle eder. UI'da disclaimer.

**P8. Hızlı ve sıfır onboarding.** Kayıt → ilk değer 60 sn'den az. Demo verisi opsiyonel yüklenebilir.

**P9. Mobile-first.** Önce telefon, sonra desktop.

**P10. Açık kaynak.** MIT lisans. Public GitHub. README ve bu doküman jüriye açık.

---

## 6. Türkiye'ye özgü hususlar

Agent ve UI bu kuralları her zaman uygular.

**Para birimi ve format:**
- Sembol: ₺ (sonra, boşlukla): `1.250,50 ₺`
- Binlik: nokta `.`
- Ondalık: virgül `,`
- Negatif: `-450,00 ₺`

**Tarih ve saat:**
- Format: `gg.aa.yyyy` (`15.05.2026`)
- Saat: 24 saat (`14:30`)
- Timezone: Europe/Istanbul (UTC+3)
- DB'de UTC, sunum yerel

**Türk perakendecileri (kategori önerisinde tanınması gerekenler):**
- Market: Migros, A101, BİM, ŞOK, CarrefourSA, Macrocenter, Tarım Kredi
- E-ticaret: Trendyol, Hepsiburada, N11, Amazon TR, Çiçeksepeti
- Yemek: Yemeksepeti, Getir, Trendyol Yemek
- Akaryakıt: Shell, Opet, BP, Petrol Ofisi
- Telekom: Turkcell, Vodafone TR, Türk Telekom

**Türk finansal kavramlar:**
- BES (Bireysel Emeklilik Sistemi)
- KKB (Kredi Kayıt Bürosu), KKB skoru
- BKM (Bankalararası Kart Merkezi)
- e-Arşiv fatura
- TROY (yerli kart)
- TÜFE (Tüketici Fiyat Endeksi)
- Türkçe banka kavramları: havale, EFT, FAST, IBAN

**Türk kültürel referanslar (çocuk modu için):**
- Harçlık (haftalık/aylık)
- Bayram parası
- Diş parası
- Kumbara

---

## 7. Glossary

Agent ve takım bu terimleri tutarlı kullanır.

| Terim | Anlam |
|---|---|
| **Cüzdan Koçu** | Ürünün adı |
| **Agent** | LangGraph state machine; LLM + tools |
| **Asistan modu** | Harcama/abonelik/fiş tool çağrıları yapan davranış |
| **Koç modu** | Finansal kavram açıklayan, senaryo simüle eden davranış |
| **Proaktif insight** | Kullanıcı sormadan veya manuel yenilemeyle worker tarafından üretilen içgörü |
| **Aile** | Aynı `family_id` altında 1+ parent ve 0+ child kullanıcılardan oluşan grup |
| **Parent** | Aile yöneticisi; ailenin tümünü görür |
| **Child** | Aile ilişkisi rolü; parent'ın çocuğu olan hesap. Reşit olabilir, sadece kendi verisini görür |
| **Age status** | `minor` / `adult`; `birth_date` üzerinden dinamik hesaplanır, kullanıcıdan manuel yaş alınmaz |
| **Individual** | Aileye bağlı olmayan tekil kullanıcı |
| **Finance level** | beginner / intermediate / advanced / child |
| **Tool** | Agent'ın çağırabildiği Python fonksiyonu (6 adet) |
| **Memory** | `agent_memory` tablosu; kalıcı kullanıcı bilgisi |
| **Insight type** | `low_activity` / `monthly_status` / `spending_spike` / `category_overspending` / `upcoming_recurring` / `savings_opportunity` / `receipt_activity` |
| **Severity** | `info` / `warning` / `critical` |
| **Transaction source** | `manual` / `receipt_ocr` / `recurring` |
| **Usage score** | 0–1 arası, abonelik kullanım yoğunluğu tahmini |
| **Recurring detection** | Aynı merchant'tan 2+ sabit tutar = abonelik tahmini |
| **Custom recurrence** | `recurrence_interval` + `recurrence_unit` ile her X gün/hafta/ay/yıl tekrarı |

---

## 8. İş kuralları (Invariants)

Bu kurallar şemaya ve mantığa kazınmıştır; bozulmaları bug'dır.

**İK-1.** Her `transactions` kaydı bir `users.id`'ye bağlıdır (NOT NULL, ON DELETE CASCADE).

**İK-2.** Tutarlar `NUMERIC(12,2)` — float yasak. TL cinsinden.

**İK-3.** Tüm `timestamp` alanları `TIMESTAMPTZ`. DB UTC, sunum yerel.

**İK-4.** `child` yalnızca kendi `user_id`'sine ait veriyi görür. Backend her sorguda `user_id` filtresi uygular.

**İK-5.** `parent` kendi `family_id` kapsamındaki parent/child üyelerin verisini görür. Eski veride `family_id` yoksa fallback: kendi + `parent_id = self.id` olan child'lar.

**İK-6.** `individual` yalnızca kendi verisini görür. Aile UI'da gizli.

**İK-7.** Tool çağrılarında `user_id` agent state'inden gelir, kullanıcı promptundan ALINMAZ (prompt injection riski).

**İK-8.** Agent başka kullanıcı verisini sızdırmaz. Aile karşılaştırması bile agregeli sunulur.

**İK-9.** `agent_memory` upsert ile yazılır (`ON CONFLICT (user_id, key) DO UPDATE`).

**İK-10.** `proactive_insights` 30 gün sonra arşivlenir (UI'da gösterilmez).

**İK-11.** Fiş OCR sonuçları `raw_ocr_data` JSONB olarak saklanır.

**İK-12.** Auth: bearer token, 7 gün, refresh yok (hackathon kapsamı).

**İK-13.** Demo verisi `is_demo=true` bayraklı; gerçek veriyle karışmaz.

**İK-14.** Chat mesajları `messages` tablosunda kalır. Context window son N mesaj (N=20).

**İK-15.** API anahtarları, fiş base64'leri, ham OCR çıktıları log'a düşmez. Sadece event tipi + user_id loglanır.

**İK-16.** Yaş manuel saklanmaz. Kullanıcı/ailenin yaşa bağlı mantığı `birth_date` üzerinden dinamik `age` ve `age_status` hesaplar. `role='child'` aile ilişkisidir; kişinin reşit olup olmaması `age_status` ile ayrıdır.

**İK-17.** Tekrarlayan kayıtlar yalnızca haftalık/aylık/yıllık seçeneklerine bağlı değildir. `billing_cycle='custom'` için `recurrence_interval >= 1` ve `recurrence_unit IN ('day','week','month','year')` zorunludur.

---

## 9. Agent davranış kuralları

Bu kurallar `SYSTEM_PROMPT` ve tool tasarımında somutlanır.

**A-1.** Dil her zaman Türkçe. Türkçe karakterler doğru.

**A-2.** Veri öncelikli — tahmin yapma, tool çağır. "Tahminen 1500 ₺" yasak.

**A-3.** Seviye uyumu:
- `child`: harçlık, oyuncak, dondurma, doğum günü hediyesi
- `beginner`: günlük dil, teknik terim ilk kullanıldığında açıkla
- `intermediate`: terim açıklamasız kullanılabilir
- `advanced`: detaylı analiz, alternatifler

**A-4.** Finansal tavsiye yasak. "X hissesini al" / "BES'e gir" / "Krediyi kapat" yasak. Bilgilendirici çerçeve: "Bu durumda bilmen gereken şeyler şunlar..."

**A-5.** Tutar formatı: `₺` ile, virgüllü. Örnek: `1.247,50 ₺`.

**A-6.** Yargılayıcı dil yasak. "Çok harcadın" yasak; "geçen aya göre X artış" nötr.

**A-7.** Proaktivite: ilgili önemli bir uyarı varsa cevap sonuna ekle.

**A-8.** Belirsizlik: "Verim yeterli değil" / "X bilgisine ihtiyacım var" diyebilir.

**A-9.** Çocukla konuşma: soyut → somut hikâye. "Faiz" → "Kumbarana 100 ₺ koydun, banka her ay 1 ₺ ekledi..."

**A-10.** Hafıza: önemli kullanıcı bilgisini (hedef, tercih) `agent_memory`'ye yaz; sonraki konuşmada `get_user_memory` ile çek.

**A-11.** Privacy refleksi: "Komşumun gelirini söyle" gibi sorularda reddet.

**A-12.** Tool hata dönerse teknik hata gösterme. "Şu an verine erişemedim, tekrar dener misin?"

---

## 10. Güvenlik ve gizlilik

- **Auth yöntemi:** Email + password (bcrypt veya argon2id), JWT 7 gün, refresh yok. Magic link / SMS / sosyal login YOK (Bölüm 12.3 stretch).
- **Veri sahipliği:** Kullanıcıya ait. Export (CSV) ve cascade delete butonları.
- **Şifreleme:** Postgres at rest (Coolify), HTTPS (Traefik).
- **Şifre hashleme:** bcrypt veya argon2id. Plain text yasak.
- **LLM sağlayıcısına gönderilen veride:** Gemini doğrudan veya OpenRouter üzerinden seçilen model kullanılsa da isim ve fiş görseli evet; IBAN, kart no, kimlik no HAYIR (regex redact).
- **Audit log:** hangi user_id için hangi tool çağrıldı (içerik değil).
- **Hesap silme:** Tek butonla cascade.
- **Çocuk veri korumacılığı:** 18 yaş altı için ekstra disclaimer.

---

## 11. Hata yönetimi

**Tool hatası (agent katmanı):**

| Hata | Davranış |
|---|---|
| Tool exception | Agent state'e error mesajı, nazik fallback |
| DB lookup boş | Boş list/dict döner, agent "veri yok" yorumlar |
| Gemini rate limit | Backoff 3 retry, sonra "yoğunluk var" |
| Vision parse hatası | "Fişi manuel ekleyebilir misin?" alternatifi |
| Network timeout | 30 sn |

**UI hatası:**

| Senaryo | Davranış |
|---|---|
| Backend 500 | Toast: "Bir sorun çıktı, tekrar dener misin?" |
| Auth expired | Login'e redirect |
| Form validation | Inline Türkçe hata |
| File upload too big | "Maks 5 MB" |

---

# BÖLÜM B — TEKNİK DETAY

## 12. Scope (kesin)

### 12.1 Core MVP (zorunlu)

1. Email + password auth (bcrypt/argon2id, JWT 7 gün, refresh yok)
2. Manuel transaction CRUD
3. Fiş yükleme + Gemini Vision OCR + otomatik kategori
4. Chat UI streaming
5. Dashboard (özet, grafik, son işlemler)
6. LangGraph agent + 6 tool
7. Demo veri seeder (Yılmaz ailesi)

### 12.2 Derece için zorunlu

8. **Proaktif insight worker** (manuel tetik + scheduler-ready kural seti)
9. **Aile modu** (parent + child + family switch)
10. **Agent memory** (`agent_memory` tablosu)
11. **README + demo video**
12. **Day 7 ürün polish ekleri** (tek işlem girişi ekranı, hesap bilgisi düzenleme,
    parent-only aile finans özeti, daraltılabilir sol menü)
13. **Çocuk lite mod (UI):** `age_status='minor'` olan aktif kullanıcıda arayüz
    otomatik olarak sadeleşir — daha sıcak renkler, büyük dokunma hedefleri,
    Türkçe çocuk dili (Cüzdanım, Hareketler, Koç, Fişlerim, Profilim), karmaşık
    bölümler (tekrarlayan ödeme yönetimi, kategori bütçesi, geçen ay
    karşılaştırma çubukları, agent araç izi) gizlenir. Yeni endpoint, yeni route
    veya yeni veri yoktur; kapsam/auth/aile kuralları değişmez. Tetikleyici
    sadece `age_status`'tür; `role='child'` aile ilişkisi olarak kalır (yetişkin
    çocuk klasik UI'yi görür).
14. **Sohbet içi grafik (chart tool):** Yeni `visualize_spending` agent tool'u
    kullanıcının kapsamı içindeki harcama verisinden bir grafik spec (`bar` /
    `pie`) döner. Frontend tool_result event'inde `chart` alanı görürse Recharts
    ile mesaj akışı içinde grafiği çizer. Veri kapsamı kuralları (İK-4..İK-8)
    aynı `visible_user_ids` üzerinden uygulanır.
15. **Sohbet geçmişi sayfası:** `GET /api/conversations` ve
    `GET /api/conversations/{id}/messages` endpoint'leri kullanıcının kendi
    `conversations`/`messages` kayıtlarını listeler (İK-4..İK-5). Frontend'de
    `/chat/history` sayfası geçmiş sohbetleri ve mesajlarını gösterir; mesaj
    içerikleri zaten DB'de var olduğundan ek migration yok.
16. **Agent memory görüntüleyici:** `GET /api/memory` kullanıcının
    `agent_memory` kayıtlarını döner; `DELETE /api/memory/{key}` ilgili anahtarı
    siler. Frontend'de `/account/memory` (veya hesap sayfasında bir bölüm)
    listeyi gösterir. Memory yalnızca o kullanıcıya aittir (İK-4'ün katı
    biçimi); aile içi paylaşım yoktur.
17. **Koç görsel anlatım (image generation):** `illustrate_concept` agent
    tool'u finansal bir kavramı (faiz, kumbara, enflasyon vb.) Gemini'nin
    görsel modelinden geçirerek bir illüstrasyon üretir. Sonuç MinIO'ya
    `is_demo=false` bucket'a yazılır ve URL chat'te `image` event'i olarak
    görünür. Sadece **Koç modunda kavram açıklama** akışı için kullanılır;
    yatırım/ürün önerisi/fiyat görsellemesi YASAK — P7 (finansal danışman
    değil) ve A-4 (tavsiye yasağı) ihlal edilemez. P5 (çocuk dilinde somut
    örnek) ile uyumlu: çocuk modunda görsel anlatımı kuvvetlendirir. Maliyet
    için her kullanıcıya günlük 10 görsel sınırı uygulanır.

### 12.3 Stretch (ÖNCE 1–11 bitmeli)

13. Sesli giriş (Web Speech API)
14. Tasarruf hedef takibi
15. Quiz modu
16. CSV export
17. Magic link auth (email-only login, parola yok)

---

## 13. Stack

| Katman | Teknoloji | Versiyon |
|---|---|---|
| Frontend | Next.js (App Router) | 15.x |
| UI | Tailwind + shadcn/ui | latest |
| Charts | Recharts | 2.x |
| Frontend pkg manager | pnpm | latest |
| Backend | FastAPI | 0.115+ |
| Python | 3.12 | |
| Backend pkg manager | uv (lockfile commit) | latest |
| Agent | LangGraph + LangChain | 0.2+ / 0.3+ |
| LLM | Gemini 2.5 Flash doğrudan veya OpenRouter üzerinden `google/gemini-2.5-flash` | `LLM_PROVIDER=gemini\|openrouter`, `langchain-google-genai`, `langchain-openai` |
| Database | PostgreSQL | 16 |
| ORM | SQLAlchemy 2.0 + Alembic | |
| Storage | MinIO (S3 uyumlu) | |
| Auth | FastAPI custom (email + password + JWT). NextAuth.js sadece frontend session taşıyıcı. | |
| Deploy | Coolify on Hetzner VPS | |
| Cron | Scheduler-ready Python worker + manuel refresh endpoint | Platform cron/APScheduler daha sonra bağlanabilir |

---

## 14. Mimari

```
┌────────────────────────────────────────────────┐
│ Next.js Frontend (port 3000)                    │
│  /dashboard  /dashboard/transactions  /chat      │
│  /receipts  /family  /account                    │
└──────────────────┬──────────────────────────────┘
                   │ HTTPS
┌──────────────────▼──────────────────────────────┐
│ FastAPI Backend (port 8000)                     │
│  /api/auth/*  /api/transactions  /api/chat/stream│
│  /api/receipts/upload  /api/insights  /api/family│
│  /api/subscriptions                              │
└──────────┬───────────────────┬──────────────────┘
           │                   │
  ┌───────▼─────────┐   ┌─────▼──────────────┐
  │ LangGraph Agent │   │ Proactive Worker   │
  │ (in-process)    │   │ (manual/cron-ready)│
  └───────┬─────────┘   └─────┬──────────────┘
           └─────────┬─────────┘
                     │
   ┌─────────────────▼───────────────────────────┐
   │ PostgreSQL 16   │ Gemini 2.5 │ MinIO        │
   └─────────────────┴────────────┴──────────────┘
```

---

## 15. PostgreSQL şeması

> **Not (v0.3):** `password_hash` kolonu `users` tablosuna eklendi (NULL'lanabilir; child satırlarında NULL, parent/individual için NOT NULL uygulama katmanında zorlanır). Tüm tablolara `updated_at TIMESTAMPTZ DEFAULT NOW()` standart kolon eklendi (ORM tarafında `onupdate=func.now()` ile otomatik güncellenir).

```sql
-- ===== KULLANICI VE AİLE =====
CREATE TABLE users (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email           TEXT UNIQUE NOT NULL,
  name            TEXT NOT NULL,
  role            TEXT NOT NULL CHECK (role IN ('parent','child','individual')),
  parent_id       UUID REFERENCES users(id) ON DELETE CASCADE,
  family_id       UUID,
  password_hash   TEXT,  -- NULL for child accounts; NOT NULL enforced at app layer for parent/individual
  birth_date      DATE,
  finance_level   TEXT DEFAULT 'beginner'
                  CHECK (finance_level IN ('beginner','intermediate','advanced','child')),
  is_demo         BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ===== KATEGORİ VE İŞLEMLER =====
CREATE TABLE categories (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID REFERENCES users(id) ON DELETE CASCADE,  -- NULL = sistem default kategorisi
  name            TEXT NOT NULL,
  icon            TEXT,
  parent_id       UUID REFERENCES categories(id),
  budget_monthly  NUMERIC(12,2),
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE transactions (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  amount            NUMERIC(12,2) NOT NULL,
  type              TEXT NOT NULL CHECK (type IN ('income','expense')),
  category_id       UUID REFERENCES categories(id),
  description       TEXT,
  merchant          TEXT,
  occurred_at       TIMESTAMPTZ NOT NULL,
  source            TEXT DEFAULT 'manual'
                    CHECK (source IN ('manual','receipt_ocr','recurring')),
  receipt_image_url TEXT,
  raw_ocr_data      JSONB,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_tx_user_date ON transactions(user_id, occurred_at DESC);
CREATE INDEX idx_tx_category ON transactions(category_id);
CREATE INDEX idx_tx_merchant ON transactions(merchant);

CREATE TABLE subscriptions (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name                        TEXT NOT NULL,
  merchant                    TEXT,
  amount                      NUMERIC(12,2) NOT NULL,
  billing_cycle               TEXT NOT NULL
                              CHECK (billing_cycle IN ('weekly','monthly','yearly','custom')),
  recurrence_interval         INT NOT NULL DEFAULT 1 CHECK (recurrence_interval >= 1),
  recurrence_unit             TEXT NOT NULL DEFAULT 'month'
                              CHECK (recurrence_unit IN ('day','week','month','year')),
  next_billing_date           DATE,
  category_id                 UUID REFERENCES categories(id),
  is_active                   BOOLEAN DEFAULT TRUE,
  detected_from_transactions  BOOLEAN DEFAULT FALSE,
  usage_score                 NUMERIC(3,2),
  created_at                  TIMESTAMPTZ DEFAULT NOW(),
  updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- ===== AGENT KATMANI =====
CREATE TABLE conversations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
  started_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE messages (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('user','assistant','tool')),
  content         TEXT NOT NULL,
  tool_calls      JSONB,
  tool_name       TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_msg_conv ON messages(conversation_id, created_at);

CREATE TABLE agent_memory (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  key         TEXT NOT NULL,
  value       JSONB NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, key)
);

CREATE TABLE proactive_insights (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  insight_type  TEXT NOT NULL,
  title         TEXT NOT NULL,
  content       TEXT NOT NULL,
  severity      TEXT DEFAULT 'info'
                CHECK (severity IN ('info','warning','critical')),
  action_label  TEXT,
  is_dismissed  BOOLEAN DEFAULT FALSE,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_insight_user ON proactive_insights(user_id, created_at DESC)
  WHERE is_dismissed=FALSE;
```

---

## 16. LangGraph agent iskeleti

```python
# backend/app/agent/graph.py
# Not (v0.7): gerçek kod LLM_PROVIDER ile doğrudan Gemini veya OpenRouter
# OpenAI-compatible endpoint seçebilir. Aşağıdaki iskelet doğrudan Gemini yolunu gösterir.
from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from .tools import (
    get_spending, get_subscriptions, analyze_receipt,
    explain_concept, simulate_scenario, get_user_memory,
    visualize_spending, illustrate_concept
)
from .prompts import build_system_prompt

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_id: str
    user_role: str          # 'parent' | 'child' | 'individual'
    finance_level: str      # 'beginner' | 'intermediate' | 'advanced' | 'child'

TOOLS = [
    get_spending, get_subscriptions, analyze_receipt,
    explain_concept, simulate_scenario, get_user_memory,
    visualize_spending, illustrate_concept,
]

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.3,
).bind_tools(TOOLS)

def agent_node(state: AgentState):
    sys = build_system_prompt(
        role=state["user_role"],
        level=state["finance_level"],
    )
    response = llm.invoke([SystemMessage(content=sys)] + list(state["messages"]))
    return {"messages": [response]}

def should_continue(state: AgentState):
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else END

workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(TOOLS))
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
workflow.add_edge("tools", "agent")

agent = workflow.compile()
```

### Tool interface'leri

```python
# backend/app/agent/tools.py
from langchain_core.tools import tool

@tool
def get_spending(user_id: str, category: str = None, days: int = 30) -> dict:
    """Kullanıcının harcama özetini döner. category boşsa tüm kategoriler."""
    ...

@tool
def get_subscriptions(user_id: str, only_active: bool = True) -> list[dict]:
    """Aktif abonelikleri ve kullanım skorlarını döner."""
    ...

@tool
def analyze_receipt(image_base64: str, user_id: str) -> dict:
    """Fiş görselinden transaction çıkarır (Gemini Vision)."""
    ...

@tool
def explain_concept(concept: str, user_level: str = "beginner") -> str:
    """Finansal kavramı seviyeye göre açıklar."""
    ...

@tool
def simulate_scenario(scenario: str, user_id: str) -> str:
    """Kullanıcı verisi üzerinde finansal senaryo simüle eder."""
    ...

@tool
def get_user_memory(user_id: str, key: str = None) -> dict:
    """Agent'in kullanıcı hakkında hatırladığı bilgileri çeker."""
    ...

@tool
def visualize_spending(user_id: str, days: int = 30, chart_type: str = "bar") -> dict:
    """Kapsam içi harcamadan bar/pie chart spec döner."""
    ...

@tool
def illustrate_concept(user_id: str, concept: str) -> dict:
    """Koç modunda finansal kavram için eğitim illüstrasyonu URL'i döner."""
    ...
```

### System prompt iskelet

```python
# backend/app/agent/prompts.py
def build_system_prompt(role: str, level: str) -> str:
    return f"""Sen Cüzdan Koçu'sun — Türk aileleri için finans asistanı ve koçu.

İki modda çalışırsın:
- ASISTAN: Harcama, gelir, abonelik, fiş analizi
- KOÇ: Finansal kavram açıklama, senaryo simülasyonu

Kullanıcının rolü: {role}, finansal seviyesi: {level}.

Kuralların:
1. Her zaman Türkçe yanıtla.
2. Veri gerektiren her soruda önce tool çağır.
3. Seviyeye göre dil ayarla.
4. Çocuk için: harçlık, oyuncak, dondurma örnekleri.
5. Tutar formatı: "1.250,00 ₺" (binlik nokta, ondalık virgül, sonra ₺).
6. Tarih formatı: "15.05.2026".
7. Yargılayıcı dil yasak.
8. Finansal tavsiye verme — bilgilendir, simüle et, yönlendirme.
9. İlgili önemli bir uyarı varsa cevabın sonuna ekle.
10. Önemli kullanıcı bilgisini agent_memory'ye yaz.
"""
```

---

## 17. Proaktif uyarı sistemi

`backend/app/workers/proactive.py` — manuel çalıştırılabilir, cron/platform scheduler'a bağlanmaya hazır job. MVP'de `POST /api/insights/refresh` tek kullanıcı/aile kapsamını yeniler; worker ise child dışı tüm kullanıcılar için toplu yenileme yapar.

**Kural 1 — Düşük aktivite / onboarding:**
```
son 30 günde görünür transaction yok
→ insight_type='low_activity', severity='info'
```

**Kural 2 — Aylık durum özeti:**
```
current_income, current_expense, balance = bu ay görünür transaction toplamları
→ insight_type='monthly_status', severity='warning' if balance < 0 else 'info'
```

**Kural 3 — Kategori artışı ve bütçe aşımı:**
```
current_category_total > previous_month_category_total * 1.25
→ insight_type='spending_spike', severity='warning'

current_category_total > categories.budget_monthly
→ insight_type='category_overspending', severity='critical'
```

**Kural 4 — Yaklaşan tekrarlayan ödeme:**
```
subscriptions.is_active=true
AND next_billing_date bugünden sonraki 7 gün içinde
→ insight_type='upcoming_recurring', severity='warning'
```

**Kural 5 — Abonelik yükü ve fiş katkısı:**
```
total_subs_monthly > current_income * 0.10
→ insight_type='savings_opportunity', severity='info'

bu ay source='receipt_ocr' transaction varsa
→ insight_type='receipt_activity', severity='info'
```

---

## 18. 8 günlük plan

Bu plan iki full-stack kişi arasında **task bazlı** paylaşılır:

- Her task tek kişiye aittir; aynı task iki kişiye yazılmaz.
- Bir task frontend + backend + test + deploy işlerini birlikte içerebilir.
- Bağımlılık varsa bu, tek yönlü teslimdir; ortak sahiplik değildir.

| Gün | Tarih | Person A | Person B |
|---|---|---|---|
| 1 | 11 May Pzt | Repo + FastAPI + Postgres + Docker Compose + Alembic + auth iskelet | Next.js init + Tailwind + shadcn + layout + route plan + chat UI mockup |
| 2 | 12 May Sal | Task 1: Auth akışı uçtan uca | Task 2: Transaction akışı + chat mock uçtan uca |
| 3 | 13 May Çar | Task 3: Agent harcama sorgusu + stream backend | Task 4: Dashboard analytics + stream chat UI |
| 4 | 14 May Per | Task 5: Receipt ingestion backend slice | Task 6: Receipt confirmation + history UI |
| 5 | 15 May Cum | Task 7: Family management uçtan uca | Task 8: Child coach experience uçtan uca |
| 6 | 16 May Cmt | Task 9: Proactive insights + deploy | Task 10: Insight UI + mobile/dark polish |
| 7 | 17 May Paz | Task 11: Smoke test + mimari diyagram + demo script | Task 12: README + demo assets + form copy |
| 8 | 18 May Pzt | Buffer + bug fix + form hazırlığı | Buffer + form hazırlığı |
| 9 | 19 May Pzt | Form gönder (öğleden önce) + son test | Form gönder + son test |

**Her gün 21:00 senkron — 30 dk Discord, ne yapıldı / yarın ne / blocker.**

**Günlük task listesi, owner'lar ve detaylar için:** `TEAM_PROTOCOL.md`

**Task bağımlılığı, branch ve review kuralları için:** `WORKDIVISION.md`

---

## 19. Repo yapısı

```
cuzdan-kocu/
├── README.md
├── docker-compose.yml
├── .env.example
├── frontend/
│   ├── app/
│   │   ├── (auth)/login/page.tsx
│   │   ├── dashboard/page.tsx
│   │   ├── chat/page.tsx
│   │   ├── receipts/page.tsx
│   │   ├── family/page.tsx
│   │   └── api/[...]/route.ts
│   ├── components/
│   │   ├── ui/                  # shadcn
│   │   ├── ChatStream.tsx
│   │   ├── ReceiptUploader.tsx
│   │   ├── SpendingChart.tsx
│   │   ├── InsightBanner.tsx
│   │   └── FamilySwitch.tsx
│   ├── lib/api.ts
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── auth.py
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── transactions.py
│   │   │   ├── receipts.py
│   │   │   ├── chat.py
│   │   │   ├── insights.py
│   │   │   └── family.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── transaction.py
│   │   │   ├── subscription.py
│   │   │   ├── conversation.py
│   │   │   ├── memory.py
│   │   │   └── insight.py
│   │   ├── agent/
│   │   │   ├── graph.py
│   │   │   ├── tools.py
│   │   │   └── prompts.py
│   │   ├── workers/
│   │   │   └── proactive.py
│   │   ├── services/
│   │   │   ├── gemini.py
│   │   │   └── ocr.py
│   │   └── utils/
│   │       ├── tl_format.py
│   │       └── date_format.py
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── seeds/
│   ├── demo_family.py
│   └── sample_receipts/
└── docs/
    ├── master_plan.md         # bu doküman
    ├── architecture.png
    └── demo_script.md
```

---

## 20. Demo senaryoları (90 saniyelik video için)

**Senaryo 1 — Fiş yükle (25 sn)**
1. Login (Yılmaz ailesi - Ayşe)
2. Receipts sekmesi, Migros fişini sürükle bırak
3. 3 sn'de parse: "Migros, 247,50 ₺, 7 ürün, kategori: Market"
4. Onayla, dashboard'a dön
5. Kategori grafiği güncel, yeni insight: "Bu ay marketteki harcaman %32 arttı"

**Senaryo 2 — Abonelik analizi (25 sn)**
1. Chat sekmesi
2. "Aboneliklerim nasıl gidiyor?"
3. Agent trace görünür: `get_subscriptions` çağrıldı
4. Cevap streaming: "Toplam 1.247 ₺ aylık. Netflix son 3 aydır kullanılmamış (skor 0.1). İptal edersen ayda 230 ₺ tasarruf."

**Senaryo 3 — Çocuğa koç modu (25 sn)**
1. Family switch'ten Elif'e (12) geç
2. UI çocuk dostu hale gelir
3. Elif yazar: "Faiz nedir?"
4. Agent `explain_concept(faiz, level=child)` çağırır
5. Cevap: "Diyelim kumbarana 100 ₺ koydun. Banka her ay 'durduğun için sağol' diye 1 ₺ ekliyor..."

**Senaryo 4 — Senaryo simülasyonu (15 sn, bonus)**
1. Mehmet yazar: "Kredi kartının asgarisini ödesem ne olur?"
2. Agent `simulate_scenario` + `get_user_memory` çağırır
3. Cevap: "Şu anki 8.400 ₺ bakiyenle, %3.66 aylık faizle, 18 ay sonra 4.700 ₺ ekstra faiz ödersin..."

---

## 21. Puanlama haritası (100 puan)

| Kategori | Puan | Nereden |
|---|---|---|
| Kullanıcı Değeri | 20 | Türk aileleri + family modu + canlı URL |
| Teknik Puan | 20 | LangGraph + Gemini Vision + Postgres + Cron + Coolify CD |
| Performans ve Doğruluk | 10 | Demo'da gerçek fiş 5 sn'de doğru parse + Türkçe kalite |
| Agentic Yapılar | 10 | State machine + 6 tool + memory + canlı trace |
| Yenilikçilik | 10 | Proaktif insight + aile/çocuk modu + Türkçe koç |
| Kullanıcı Dostu | 10 | Canlı URL + mobile + dark + zero onboarding |
| Takım Çalışması | 10 | Dengeli task paylaşımı + tek sahipli görevler + temiz handoff |
| Sunum | 10 | (Sadece ilk 10'a kalırsak) — şu an için README + demo video kalitesi |

---

## 22. Riskler ve Plan B

| Risk | Olasılık | Etki | Plan B |
|---|---|---|---|
| Gemini Vision Türk fişinde başarısız | Orta | Yüksek | 5 demo fişi önceden parse edilmiş JSON yedek, "demo modu" toggle |
| LangGraph 1 günü aşar | Düşük | Orta | Custom while-loop tool calling yedek |
| Coolify deploy gün 6'da sorun | Düşük | Kritik | Vercel + Railway yedek; localhost demo video |
| Türkiye IP Gemini API limit | Düşük | Yüksek | `LLM_PROVIDER=openrouter` ile OpenRouter yedeği |
| Demo veri seed çalışmaz | Orta | Orta | Manuel script + JSON fixture |
| Takım üyesi hasta | Düşük | Yüksek | Full-stack ikisi de, GitHub commit + günlük senkron |
| Form son dakika sorun | Düşük | Kritik | Form 18 Mayıs öğleden sonra gönderilecek |

---

## 23. Submission checklist

Form doldurulmadan önce hazır olmalı:

- [ ] Canlı çalışan URL (Coolify'da, Türkiye'den açılır)
- [ ] Public GitHub repo (MIT lisans)
- [ ] README: banner + 30 sn GIF + tech stack + canlı URL + kurulum + demo aile bilgisi
- [ ] Demo video (60-120 sn, ekran kaydı + Türkçe voice-over)
- [ ] Mimari diyagramı PNG
- [ ] Master plan dosyası `/docs/master_plan.md`
- [ ] Demo Yılmaz ailesi credentials: `ayse@demo.cuzdan-kocu.app` / `demo123`
- [ ] Form alanları için hazır içerik (proje adı, kısa açıklama, uzun açıklama, ekip)

---

## 24. README için sunum vurguları

GitHub README'de jüri görür:

1. Banner görsel + tagline ("Türk aileleri için proaktif finans koçu")
2. 30 saniyelik animasyonlu GIF demo
3. "7 günde 2 öğrenci tarafından inşa edildi" rozeti
4. Tech stack rozetleri
5. **Canlı URL** ve test hesabı
6. Mimari diyagram
7. 4 ana özelliğin gif'leri (fiş, chat, insight, family)
8. Kurulum: `docker-compose up`
9. Mimari notlar (bu dokümana link)
10. Lisans: MIT

---

## 25. Sunum yapısı (sadece ilk 10'a kalırsak — 7 dk)

| Sn | Bölüm | Sahip | İçerik |
|---|---|---|---|
| 0–30 | Problem | Person B | 3 stat: aileler + okuryazarlık + çocuk |
| 30–90 | Çözüm | Person B | 1 cümle tanım + 3 ekran |
| 90–270 | Canlı demo | Person B | 3 senaryo: fiş → abonelik → çocuğa koç |
| 270–360 | Mimari | Person A | Diyagram + LangGraph state machine |
| 360–390 | Agentic vurgu | Person A | Canlı agent trace |
| 390–420 | Yenilikçilik + kapanış | Person B | Proaktif + aile + Türkçe + canlı URL |

İlk 10 açıklandıktan sonra detayları yazılacak.

---

## 26. Doğrulanması gereken varsayımlar

Bu maddeler Faruk + takım arkadaşı tarafından onaylanmalı; aksi halde değişir:

1. Parent ailesinin tüm verilerini görür, child sadece kendi verisini görür.
2. Hesap kaydı email + password (bcrypt veya argon2id) ile. JWT 7 gün, refresh yok. SMS yok, sosyal login yok. Magic link Bölüm 12.3 stretch'e alındı.
3. Aboneliğin "kullanım skoru" basitçe son 90 gün transaction varlığıyla hesaplanır; banka API entegrasyonu yok.
4. Çocuk hesabını parent yaratır, child kendi kayıt olamaz.
5. Lisans MIT, GitHub repo public.
6. Demo video çekiminde gerçek bir Türk fişi (sahte amount'lar) kullanılacak.
7. İlk versiyon tek banka entegrasyonu yok; tüm veri manuel veya OCR.
8. KVKK detayı için yalnızca disclaimer, gerçek uyum süreci hackathon dışı.

---

## 27. Coding agent için talimat (TL;DR)

Coding agent (Claude Code/Cursor/Aider) ile çalışırken:

1. Her yeni feature başlamadan önce ilgili user story (US-1..US-10) ve iş kuralları (İK-1..İK-15) kontrol et.
2. Veri yazan her endpoint'te `user_id` filtresi olmalı (İK-4, İK-5).
3. Tutar = `NUMERIC(12,2)`, tarih = `TIMESTAMPTZ` (İK-2, İK-3).
4. Türkçe metin, TL formatı, Türk tarih (Bölüm 6).
5. Agent tool çağrılarında `user_id` LLM'den değil state'ten alınır (İK-7).
6. Yeni özellik scope dışıysa Bölüm 12.3 stretch'e ekle, doğrudan kodlama.
7. Tasarım prensiplerine aykırı bir karar varsa kodlamaya başlamadan dokümanı güncelle.
8. Şifreler bcrypt/argon2 (Bölüm 10), API anahtarları log'a düşmez (İK-15).
9. Demo veri `is_demo=true` ile işaretli (İK-13).
10. Son commit'ten önce kontrol: tüm UI metinleri Türkçe mi? Tüm tutarlar `₺` ile mi? Tüm tarihler `gg.aa.yyyy` mi?
11. Her tabloda `created_at` + `updated_at` ikilisi var. SQLAlchemy model: `Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())`.

---

**Doküman versiyonu:** 0.13
**Son güncelleme:** 13 Mayıs 2026
**v0.13 değişiklikleri:** §16 LangGraph iskeleti v0.12 scope ile hizalandı:
`visualize_spending` ve `illustrate_concept` araçları import, `TOOLS` listesi ve
tool interface örneklerine eklendi. Kapsam/sözleşme değişmedi; v0.12'de eklenen
sohbet içi grafik ve koç görsel anlatım kararları netleştirildi.
**v0.12 değişiklikleri:** §12.2'ye 14–17 maddeleri eklendi: sohbet içi grafik
(chart tool), sohbet geçmişi sayfası, agent memory görüntüleyici ve koç görsel
anlatım (image generation) aracı. Image generation P7/A-4'ü ihlal etmemek için
sadece kavram açıklama akışına bağlandı; kullanıcı başına günlük 10 görsel
sınırı, sonuç MinIO'da `is_demo=false` bucket'ta saklanır. Yeni SSE event tipi
`image`, chart için ise tool_result.result.chart şeması frontend tarafından
algılanır. İK-4..İK-8 ve İK-15 değişmedi.
**v0.11 değişiklikleri:** §12.2'ye 13. madde olarak "Çocuk lite mod (UI)" eklendi.
`age_status='minor'` olan aktif kullanıcıda (kendisi giriş yapmış olsa da, ebeveynin
family-switch ile geçtiği çocuk profili olsa da) arayüz otomatik olarak çocuk dostu
sade moda geçer. Yeni route, endpoint veya veri kolonu eklenmedi; tema, sidebar
etiketleri, panel/sohbet/fiş ekranı sadeleştirildi. P5 (çocuk dilinde somut örnek)
ilkesi UI katmanına taşındı. Backend kapsamı (İK-4..İK-8) değişmedi.
**v0.10 değişiklikleri:** Aile modelinde ilişki rolü (`role`) ile yaş statüsü (`age_status`)
ayrıldı; manuel `age` yerine `birth_date` tek kaynak oldu. `family_id` ile iki parent +
birden çok child aynı aile kapsamına alınır. Tekrarlayan kayıtlar `custom` seçenekle her X
gün/hafta/ay/yıl destekler.
**v0.9 değişiklikleri:** Day 7 ürün polish kapsamı eklendi: işlem ve tekrarlayan ödeme
girişi tek `İşlemler` ekranında birleşir; kullanıcı hesap bilgilerini düzenleyebilir;
ebeveynler parent-only aile finans özetini görebilir; geniş ekran için sol menü
daraltılabilir. Bu ekler mevcut aile/veri kapsamı kurallarını değiştirmez.
**v0.8 değişiklikleri:** Proaktif insight kapsamı mevcut implementasyona göre güncellendi: manuel refresh endpoint'i, scheduler-ready worker, `low_activity`, `monthly_status`, `spending_spike`, `category_overspending`, `upcoming_recurring`, `savings_opportunity`, `receipt_activity` tipleri ve cron/APScheduler bağlama notu eklendi.
**v0.7 değişiklikleri:** LLM sağlayıcı seçimi eklendi: doğrudan Gemini varsayılan kalır, OpenRouter `LLM_PROVIDER=openrouter` ile yedek yol olarak desteklenir; §10 gizlilik ifadesi sağlayıcı bağımsız hale getirildi, §13 stack satırı ve §22 risk planı güncellendi.
**Sonraki güncelleme:** Handoff/ownership planı değişirse ya da yeni varsayım onayı geldiğinde.
