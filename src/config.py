# لیست ارزهای دیجیتال برای بررسی - نمادهای سازگار با KuCoin
CRYPTOCURRENCIES = [
    "BTC-USDT", "ETH-USDT", "BNB-USDT", "SOL-USDT", "XRP-USDT",
    "ADA-USDT", "DOGE-USDT", "SHIB-USDT", "DOT-USDT", 
    "LTC-USDT", "AVAX-USDT", "LINK-USDT", "UNI-USDT", "ATOM-USDT",
    # ... (لیست کامل همان‌طور که در نسخه قبلی بود باقی می‌ماند)
    "QKC-USDT"
]

# جایگزین کردن نمادهای غیر پشتیبانی شده
KUCOIN_SUPPORTED_PAIRS = {
    "MATIC-USDT": "POLY-USDT",
}

# تنظیمات استراتژی اسکالپینگ با سیستم امتیازدهی
SCALPING_SETTINGS = {
    'rsi_period': 14,
    'rsi_overbought': 70,  # افزایش برای دقت بیشتر
    'rsi_oversold': 30,    # کاهش برای حساسیت بیشتر
    'ema_short': 8,
    'ema_medium': 21,
    'ema_long': 50,
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9,
    'bb_period': 20,
    'bb_std': 2.5,
    'min_volume_threshold': 1000000,  # فیلتر حداقل حجم معاملات (USDT)
    'volume_change_threshold': 1.5,
    'profit_target_percent': 1.5,
    'stop_loss_percent': 0.8,
    'min_score_threshold': 75,  # افزایش برای کیفیت بالاتر
    'trend_confirmation_weight': 20,  # وزن کمتر برای تایم فریم بالاتر
    'max_signals_per_symbol': 1,  # حداکثر سیگنال فعال برای هر ارز
    'signal_cooldown_minutes': 15,  # خنک‌سازی برای سیگنال‌های متوالی
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
