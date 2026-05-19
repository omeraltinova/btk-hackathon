# Eklenen Özellikler İçin Manuel Test Rehberi

Bu rehber, son eklenen demo/polish özelliklerinin elle kontrol edilmesi içindir.

## 1. Projeyi Çalıştırma

Önce Docker Desktop açık ve tamamen hazır olmalı. Docker çalışmıyorsa:

```bash
open -a Docker
docker info
```

`docker info` hata vermeden çalıştıktan sonra repo kök dizininde şu komutları çalıştır:

```bash
docker compose up -d --build
docker compose exec backend uv run alembic upgrade head
docker compose exec backend uv run python -m app.workers.demo_seed
```

Frontend adresi:

```text
http://localhost:3000
```

Demo giriş bilgisi:

```text
ayse@demo.cuzdan-kocu.app
demo123
```

## 2. Bildirim Merkezi

Eklenen yerler:

- `frontend/components/NotificationBell.tsx`
- `frontend/components/sidebar.tsx`
- `backend/app/services/insights.py`
- `backend/tests/test_insights.py`

Ne eklendi:

- Sidebar içine `Bildirim` butonu eklendi.
- Buton mevcut scoped `/api/insights` verisini okur.
- Açık bildirim sayısını rozet olarak gösterir.
- Açılır panelde son koç notlarını gösterir.
- Bildirim `X` ile kapatılabilir.
- Insight yenileme artık aynı açık bildirimi tekrar tekrar çoğaltmaz; mevcut bildirimi günceller.

Nasıl test edilir:

1. Giriş yaptıktan sonra sidebar üstündeki `Bildirim` butonuna tıkla.
2. `Bildirim merkezi` ve `Koç notları` panelinin açıldığını kontrol et.
3. Bir bildirimi `X` ile kapat.
4. Sayfayı yenile.
5. Kapatılan bildirimin hemen geri gelmediğini kontrol et.
6. Aile/aktif profil değiştirilebiliyorsa çocuk profile geç ve bildirimlerin yenilendiğini kontrol et.

Beklenen sonuç:

- Bildirim paneli açılır.
- Bildirim sayısı doğru görünür.
- Kapatılan bildirim listeden düşer.
- Aynı bildirim yenilemede tekrar tekrar çoğalmaz.

## 3. Güvenli Agent Hafızası Yazma

Eklenen yerler:

- `backend/app/agent/tools.py`
- `backend/app/services/agent_runner.py`
- `backend/app/agent/prompts.py`
- `backend/tests/test_agent_tools.py`
- `backend/tests/test_chat_stream.py`

Ne eklendi:

- Kullanıcı açıkça `Bunu hatırla:` dediğinde agent aktif profil için hafıza kaydı yazar.
- Yeni tool: `remember_user_memory`.
- Hafıza yazma canlı LLM yolundan önce deterministik olarak çalışır.
- Prompt içinden gelen `user_id` kullanılmaz; aktif profil scope'u kullanılır.
- Hassas bilgiler hafızaya yazılmaz.
- Bloklanan hassas metin tool trace içinde de redakte edilir.

Engellenen hassas örnekler:

- Şifre/parola
- Token/JWT/API key/secret
- IBAN
- Kart numarası
- TC kimlik numarası
- Ham OCR
- Base64 benzeri uzun veri
- Fiş görseli/base64 içeriği

Nasıl test edilir:

1. `/chat` sayfasına git.
2. Şunu gönder:

```text
Bunu hatırla: kahveyi şekersiz içerim
```

3. Beklenen cevap: aktif profil hafızasına kaydedildiğini söylemeli.
4. `/account/memory` sayfasına git.
5. `kahveyi şekersiz içerim` bilgisinin listede olduğunu kontrol et.
6. Tekrar `/chat` sayfasına dön ve şunu gönder:

```text
Bunu hatırla: IBAN TR120006200119000006672315
```

7. Beklenen cevap: bilgi hassas göründüğü için kaydetmediğini söylemeli.
8. `/account/memory` sayfasında IBAN bilgisinin olmadığını kontrol et.

Beklenen sonuç:

- Açık onaylı normal bilgi hafızaya yazılır.
- Hassas bilgi reddedilir ve hafızaya yazılmaz.

## 4. Sesli Koç

Eklenen yerler:

- `frontend/components/ChatStream.tsx`
- `frontend/app/(app)/chat/page.tsx`
- `docs/master_plan.md`

Ne eklendi:

- Tarayıcı destekliyorsa Web Speech API ile sesli giriş eklendi.
- Asistan yanıtını sesli okuma seçeneği eklendi.
- Çocuk modunda sesli okuma varsayılan olarak açık olur.
- Chat sayfasındaki büyük hero kaldırıldı; sohbet alanı daha geniş hale getirildi.

Nasıl test edilir:

1. Chrome ile `/chat` sayfasını aç.
2. Mikrofon ikonu görünüyorsa tıkla.
3. Tarayıcı mikrofon izni isterse izin ver.
4. Kısa bir Türkçe cümle söyle.
5. Metnin input alanına geldiğini kontrol et.
6. `Sesli oku açık/kapalı` düğmesini değiştir.
7. Bir mesaj gönder.
8. Sesli okuma açıksa asistan cevabının okunmasını kontrol et.

Beklenen sonuç:

- Destekleyen tarayıcıda konuşma metne çevrilir.
- Sesli okuma açıkken asistan cevabı okunur.
- Desteklemeyen tarayıcıda normal yazılı chat çalışmaya devam eder.

## 5. Fiş Sonrası Koça Sorma Akışı

Eklenen yerler:

- `frontend/components/ReceiptUploader.tsx`
- `frontend/lib/chat-session.ts`

Ne eklendi:

- Fiş onaylanıp işleme dönüştükten sonra başarı kartı gösterilir.
- Başarı kartında `Koça sor` butonu eklendi.
- Buton, ilgili satıcı hakkında chat'e hazır soru taşır.

Nasıl test edilir:

1. `/transactions` sayfasına git.
2. Bir fiş görseli yükle.
3. OCR sonucunu onayla ve işlem oluştur.
4. `Fiş işleme dönüştü.` başarı kartını gör.
5. `Koça sor` butonuna tıkla.
6. `/chat` sayfasına yönlendirildiğini kontrol et.
7. Satıcıya göre hazırlanmış harcama sorusunun chat'te başladığını kontrol et.

Beklenen sonuç:

- Fiş işlem olarak kaydedilir.
- Başarı kartı görünür.
- `Koça sor` chat'e doğru bağlamla gider.

## 6. Hedef Şablonları, Milestone Toast ve İlgili Harcamalar

Eklenen yerler:

- `frontend/components/SavingGoalsClient.tsx`
- `frontend/lib/kid-mode.tsx`

Ne eklendi:

- Birikim hedefleri için hızlı şablonlar eklendi.
- Çocuk modunda farklı hedef şablonları gösterilir.
- Hedef ilerlemesi %25, %50, %75 veya %100 eşiklerini geçince toast gösterilir.
- Gider azaltma hedefi detayında ilgili son harcamalar gösterilir.
- İlgili harcama listesi hem `goal.user_id` hem `category_id` ile filtrelenir.

Nasıl test edilir:

1. `/goals` sayfasına git.
2. `Birikim` modunda hızlı şablonlardan birine tıkla.
3. Hedef adı ve tutarın otomatik dolduğunu kontrol et.
4. Hedef oluştur.
5. Birikim hedefine katkı ekle.
6. İlerleme %25, %50, %75 veya %100 eşiğini geçerse toast çıktığını kontrol et.
7. Bir gider azaltma hedefini seç.
8. Detay panelinde ilgili son hareketler listesini kontrol et.

Beklenen sonuç:

- Şablonlar formu doldurur.
- Katkı eklenince ilerleme güncellenir.
- Eşik geçişlerinde tebrik toast'ı görünür.
- İlgili harcamalar sadece seçili hedefin sahibi ve kategorisine göre listelenir.

## 7. Dashboard Ay Sonu Projeksiyonu

Eklenen yerler:

- `frontend/components/dashboard-client.tsx`

Ne eklendi:

- Dashboard'a `Ay sonu projeksiyonu` kartı eklendi.
- Bugüne kadarki harcama temposundan ay sonu gider tahmini gösterilir.
- Kalan bütçeye göre güvenli günlük tempo gösterilir.

Nasıl test edilir:

1. `/dashboard` sayfasına git.
2. `Ay sonu projeksiyonu` kartını bul.
3. `Mevcut hızla` değerini kontrol et.
4. `Güvenli günlük tempo` değerini kontrol et.
5. Para formatının Türkçe olduğunu kontrol et.

Beklenen para formatı:

```text
1.250,00 ₺
```

## 8. Lisans Dosyası

Eklenen yerler:

- `LICENSE`
- `README.md`

Ne eklendi:

- MIT lisans dosyası eklendi.
- README lisans bölümü `LICENSE` dosyasına bağlandı.

Nasıl test edilir:

1. Repo kökünde `LICENSE` dosyasının olduğunu kontrol et.
2. `README.md` içindeki lisans linkinin `LICENSE` dosyasını gösterdiğini kontrol et.

## 9. Otomatik Doğrulama Komutları

Manuel testten önce veya sonra şu komutlarla otomatik kontroller yapılabilir.

Backend:

```bash
cd backend
uv run pytest -q
uv run ruff check app tests
uv run ruff format --check app tests
uv run python -m mypy app
```

Frontend:

```bash
cd frontend
npx pnpm@11.0.9 type-check
npx pnpm@11.0.9 lint
npx pnpm@11.0.9 format:check
npx pnpm@11.0.9 build
```

Repo kökünde:

```bash
git diff --check
```

Build uyarısı beklentisi:

```text
The Next.js plugin was not detected in your ESLint configuration
```

Bu uyarı artık beklenmez. `next build` sırasında tekrar görünürse P0'da yapılan
sessiz build düzeltmesi gerilemiş demektir; build başarılı olsa bile kontrol edilmelidir.

## 10. Bu Rehberin Kapsamı Dışında Olanlar

Bu rehber P0 teslim paketi için değildir.

Bu rehber otomatik browser testi içermez; kontroller elle yapılmalıdır.
