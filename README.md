# CEX Listing Research Dashboard

Tracks new token listings across 8 major CEXs in 2026. Data sourced from [listedon.org](https://listedon.org).

**Exchanges covered:** Binance, OKX, Coinbase, Gate.io, KuCoin, MEXC, Kraken, Upbit

## Quickstart

```bash
pip install -r requirements.txt

# View dashboard (data already included)
streamlit run dashboard.py

# Update with latest listings
python scraper.py
```

## Dashboard

- Monthly listing trends by exchange
- Exchange comparison
- Tokens listed on multiple exchanges (cross-listing analysis)
- Full data table with CSV export
