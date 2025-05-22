# لیست ارزهای دیجیتال برای بررسی - نمادهای سازگار با KuCoin# لیست ارزهای دیجیتال برای بررسی - نمادهای سازگار با KuCoin
CRYPTOCURRENCIES = [
    "BTC-USDT", "ETH-USDT", "BNB-USDT", "SOL-USDT", "XRP-USDT",
    "ADA-USDT", "DOGE-USDT", "SHIB-USDT", "DOT-USDT", 
    "LTC-USDT", "AVAX-USDT", "LINK-USDT", "UNI-USDT", "ATOM-USDT",
    "TRX-USDT", "NEAR-USDT", "MATIC-USDT", "APT-USDT",
    "PEPE-USDT", "ICP-USDT", "ETC-USDT", "XLM-USDT", "HBAR-USDT",
    "INJ-USDT", "VET-USDT", "CRO-USDT", "OP-USDT", "ALGO-USDT",
    "GRT-USDT", "SUI-USDT", "AAVE-USDT", "FTM-USDT", "FLOW-USDT",
    "AR-USDT", "EGLD-USDT", "AXS-USDT", "CHZ-USDT", "SAND-USDT",
    "MANA-USDT", "NEO-USDT", "KAVA-USDT", "XTZ-USDT", "KCS-USDT",
    "MINA-USDT", "GALA-USDT", "ZIL-USDT", "ENJ-USDT", "1INCH-USDT",
    "HOT-USDT", "COMP-USDT", "ZEC-USDT", "RVN-USDT", "BAT-USDT",
    "DASH-USDT", "WAXP-USDT", "LRC-USDT", "QTUM-USDT", "ICX-USDT",
    "ONT-USDT", "WAVES-USDT", "KSM-USDT", "CHR-USDT",
    "ANKR-USDT", "OCEAN-USDT", "IOST-USDT", "SC-USDT", "RSR-USDT",
    "DCR-USDT", "SYS-USDT", "GLMR-USDT", "BICO-USDT", "COTI-USDT",
    "SKL-USDT", "BAL-USDT", "LPT-USDT", "CELR-USDT", "DGB-USDT",
    "XYO-USDT", "API3-USDT", "OMG-USDT", "POWR-USDT", "SXP-USDT",
    "REQ-USDT", "VTHO-USDT", "XEM-USDT", "NKN-USDT", "CTSI-USDT",
    "STPT-USDT", "FLUX-USDT", "PUNDIX-USDT", "STRAX-USDT", "AUDIO-USDT",
    "ARDR-USDT", "STEEM-USDT", "CVC-USDT", "SNT-USDT", "DENT-USDT",
    "HIVE-USDT", "LOOM-USDT", "ARK-USDT", "TLM-USDT", "RLC-USDT",
    "NMR-USDT", "SLP-USDT", "AGLD-USDT", "FORTH-USDT", "REI-USDT",
    "PHA-USDT", "AERGO-USDT", "CLV-USDT", "TRAC-USDT", "LTO-USDT",
    "MLN-USDT", "RIF-USDT", "GHST-USDT", "DUSK-USDT", "BAND-USDT",
    "ORBS-USDT", "UOS-USDT", "ERN-USDT", "MDT-USDT", "KMD-USDT",
    "WNCG-USDT", "QKC-USDT"
]

# جایگزین کردن نمادهای غیر پشتیبانی شده
KUCOIN_SUPPORTED_PAIRS = {
    "MATIC-USDT": "POLY-USDT",
}

# تنظیمات استراتژی اسکالپینگ با سیستم امتیازدهی
SCALPING_SETTINGS = {
    'rsi_period': 14,
    'rsi_overbought': 70,
    'rsi_oversold': 30,
    'ema_short': 8,
    'ema_medium': 21,
    'ema_long': 50,
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9,
    'bb_period': 20,
    'bb_std': 2.5,
    'volume_change_threshold': 2.0,
    'profit_target_percent': 1.5,
    'stop_loss_percent': 0.8,
    'min_score_threshold': 75,
    'trend_confirmation_window': 20,
}

# تنظیمات تایم فریم‌ها
PRIMARY_TIMEFRAME = "30min"
HIGHER_TIMEFRAME = "1hour"
KLINE_SIZE = 500
SIGNALS_FILE = "data/signals.json"

# تنظیمات API کوکوین
KUCOIN_BASE_URL = "https://api.kucoin.com"
KUCOIN_KLINE_ENDPOINT = "/api/v1/market/candles"
KUCOIN_TICKER_ENDPOINT = "/api/v1/market/orderbook/level1"