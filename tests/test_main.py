import main

SAMPLE = {"source":"test","fetched_at":1700000000,"cache":"hit","fiyatlar":[
 {"kod":"ceyrek_eski","kategori":"sarrafiye_eski","alis":10100,"satis":10450},
 {"kod":"ceyrek_altin","kategori":"sarrafiye_yeni","alis":9950,"satis":10200},
 {"kod":"18_ayar","kategori":"ayar","alis":5600,"satis":6530},
 {"kod":"dolar","kategori":"doviz","alis":46.88,"satis":47.54},
 {"kod":"euro","kategori":"doviz","alis":53.88,"satis":54.68},
 {"kod":"ons_usd","kategori":"doviz","alis":4095.13,"satis":4095.54}]}

def test_gold_normalization():
    products = main.normalize_gold(SAMPLE)
    assert [item["urun_kodu"] for item in products] == ["ceyrek_kapali", "ceyrek_acik", "22_ayar_iscilik"]
    assert "urun_turu" not in products[0]

def test_market_normalization():
    assets = main.normalize_markets(SAMPLE)
    assert [item["varlik_kodu"] for item in assets] == ["USD", "EUR", "XAU_ONS_USD"]
    assert assets[0]["para_birimi"] == "TRY"
    assert assets[2]["para_birimi"] == "USD"
