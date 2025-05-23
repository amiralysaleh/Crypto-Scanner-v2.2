# لیست ارزهای دیجیتال برای بررسی - نمادهای سازگار با KuCoin
CRYPTOCURRENCIES = [
    "BTC-USDT", "ETH-USDT", "BNB-USDT", "SOL-USDT", "XRP-USDT",
    "ADA-USDT", "DOGE-USDT", "SHIB-USDT", "DOT-USDT",
    "LTC-USDT", "AVAX-USDT", "LINK-USDT", "UNI-USDT", "ATOM-USDT",
    # ... (بقیه لیست همان‌طور که در نسخه اصلی بود باقی می‌ماند)
    "QKC-USDT"
]

# جایگزین کردن نمادهای غیر پشتیبانی شده
KUCOIN_SUPPORTED_PAIRS = {
    "MATIC-USDT": "POLY-USDT",
}

# تنظیمات استراتژی اسکالپینگ با سیستم امتیازدهی
SCALPING_SETTINGS = {
    'rsi_period': 14,
    'rsi_overbought': 70,  # استانداردتر برای بازار ارزهای دیجیتال
    'rsi_oversold': 30,
    'ema_short': 8,
    'ema_medium': 21,
    'ema_long': 50,
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9,
    'bb_period': 20,
    'bb_std': 2.0,  # کاهش برای حساسیت بیشتر
    'min_volume_threshold': 500000,  # حداقل حجم معاملات 24 ساعته (USDT)
    'volume_change_threshold': 1.5,
    'profit_target_multiplier': 2.0,  # ضریب هدف سود بر اساس ATR
    'stop_loss_multiplier': 1.5,     # ضریب حد ضرر بر اساس ATR
    'min_score_threshold': 75,       # حداقل امتیاز برای سیگنال
    'min_risk_reward_ratio': 1.5,    # حداقل نسبت ریسک به ریوارد
    'signal_cooldown_minutes': 15,   # خنک‌سازی برای سیگنال‌های متوالی
    'max_signals_per_symbol': 1,     # حداکثر سیگنال فعال برای هر ارز
    'trend_confirmation_window': 10,
    'fee_percent': 0.1,              # کارمزد معاملات KuCoin
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
KUCOIN_STATS_ENDPOINT = "/api/v1/market/stats"  # برای بررسی حجم معاملات
