# Altin ve Doviz Fiyat API

Bu servis `erkuder.com` uzerinden fiyatlari alir, 5 dakika boyunca lokal cache dosyasinda saklar ve API olarak dondurur.

## Kurulum

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Calistirma

```bash
uvicorn main:app --reload
```

## Endpointler

- `GET /fiyatlar`: Tum fiyat listesini dondurur.
- `GET /health`: Basit saglik kontrolu.

Ornek:

```bash
curl http://127.0.0.1:8000/fiyatlar
```

Cache dosyasi `cache/prices.json` olarak yazilir. Cache 5 dakikadan eskiyse yeni veri cekilir. Kaynak siteye ulasilamazsa ve eski cache varsa API eski cache'i `cache: "stale"` bilgisiyle dondurur.


## Production

Production'da uygulamayi internete dogrudan `uvicorn --host 0.0.0.0` ile acmak yerine `systemd` ile localhost'ta calistirip nginx ile disari yayinlayin.

### 1. Ortam dosyasi

```bash
cp .env.example .env
nano .env
```

Guclu bir API key uretmek icin:

```bash
openssl rand -hex 32
```

### 2. Servis kurulumu

`deploy/altin-fiyat-api.service` dosyasindaki `User`, `Group` ve path degerlerini sunucuya gore kontrol edin.

```bash
sudo cp deploy/altin-fiyat-api.service /etc/systemd/system/altin-fiyat-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now altin-fiyat-api
sudo systemctl status altin-fiyat-api
```

### 3. Nginx reverse proxy

`deploy/nginx.conf` icindeki `server_name` degerini kendi domaininizle degistirin.

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/altin-fiyat-api
sudo ln -s /etc/nginx/sites-available/altin-fiyat-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

HTTPS icin:

```bash
sudo certbot --nginx -d api.example.com
```

### 4. Istek ornekleri

```bash
curl -H "X-API-Key: API_KEY_DEGERI" https://api.example.com/fiyatlar
```
