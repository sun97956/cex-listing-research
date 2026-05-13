# CEX Listing Research Dashboard

Tracks new token listings across 6 major CEXs + Binance Futures in 2026. Spot data sourced from [listedon.org](https://listedon.org), Futures data from Binance official API.

**Exchanges covered:** Binance (Spot + Futures), OKX, ByBit, Coinbase, Bithumb, Upbit

## Quickstart

```bash
pip install -r requirements.txt

# View dashboard (data already included)
streamlit run dashboard.py

# Update with latest listings
python scraper.py
python binance_futures.py

# Update with latest listings
python scraper.py
```

## Dashboard

- Monthly listing trends by exchange
- Exchange comparison
- Tokens listed on multiple exchanges (cross-listing analysis)
- Full data table with CSV export
