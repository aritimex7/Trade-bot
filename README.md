# 🤖 Polymarket Trading Bot

Bot trading otomatis untuk Polymarket dengan strategi **Mean-Reversion Agresif**.  
Dioptimalkan untuk modal kecil ($10) dengan AI analysis.

## 📦 Instalasi

```powershell
# 1. Clone/download ke folder ini
cd c:\Users\USER\.gemini\antigravity\scratch\openclaw

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy dan edit .env
copy .env.example .env
# Edit .env dengan credentials kamu
```

## 🔑 Setup Credentials

Edit file `.env`:

```env
PRIVATE_KEY=0x...your_wallet_private_key...
PM_API_KEY=your_api_key
PM_API_SECRET=your_api_secret
PM_API_PASSPHRASE=your_passphrase
```

> ⚠️ **PENTING**: Private key diperlukan untuk sign orders. Jangan share file ini!

## 🚀 Menjalankan Bot

```powershell
# Test koneksi API
python -m pm_bot.main --test-api

# Dry run (tanpa trading nyata)
python -m pm_bot.main --dry-run

# Live trading
python -m pm_bot.main

# Cek status
python -m pm_bot.main --status

# Lihat AI report
python -m pm_bot.main --report
```

## 📊 Strategi

| Parameter | Value |
|-----------|-------|
| Max Trade | $0.50 |
| Max Positions | 3 |
| Z-Score Buy | < -1.2 |
| Z-Score Sell | > +1.2 |
| Stop Loss | 15% |
| Take Profit | 25% |
| Trailing Stop | 10% |
| Max Daily Loss | 2% |

## 📁 Struktur File

```
openclaw/
├── .env              # Credentials (buat dari .env.example)
├── config.py         # Semua parameter trading
├── history.csv       # Log trades (auto-generated)
├── risk_state.json   # State positions (auto-generated)
└── pm_bot/
    ├── main.py       # Entry point
    ├── data_client.py    # API client
    ├── risk_manager.py   # Risk management
    ├── math_engine.py    # Trading formulas
    └── ai_analyzer.py    # AI trade analysis
```

## 🤖 AI Analysis

Bot akan otomatis:
- Log semua trades ke `history.csv`
- Analisis win rate, profit factor, expectancy
- Generate optimization suggestions
- Print daily report setiap jam

## ⚠️ Disclaimer

- Ini adalah software eksperimental
- Trading crypto/prediction markets memiliki risiko tinggi
- Gunakan dengan bijak dan risiko sendiri
