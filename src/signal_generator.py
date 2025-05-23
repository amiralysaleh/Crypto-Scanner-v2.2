from datetime import datetime
import pytz
from config import SCALPING_SETTINGS

def calculate_score(buy_factors, sell_factors, atr, current_price):
    """محاسبه امتیاز سیگنال با وزن‌دهی متعادل"""
    max_score = 100
    score = 0
    weights = {
        'rsi': 25, 'ema': 20, 'macd': 20, 'bb': 15,
        'volume': 10, 'support': 10, 'resistance': 10,
        'price_action': 10, 'higher_tf': 10
    }
    for factor in buy_factors | sell_factors:
        score += weights.get(factor, 0)
    # تنظیم امتیاز بر اساس نوسانات (ATR)
    volatility_factor = max(0.6, min(1.0, 1.0 - (atr / current_price)))
    return min(int(score * volatility_factor), max_score)

def generate_signals(df_primary, df_higher, symbol):
    """تولید سیگنال‌های خرید و فروش با فیلترهای متعادل"""
    if df_primary is None or len(df_primary) < SCALPING_SETTINGS['trend_confirmation_window']:
        return []
    if df_higher is None or len(df_higher) < 2:
        return []

    signals = []
    latest_row = df_primary.iloc[-1]
    prev_row = df_primary.iloc[-2]
    higher_tf_trend = df_higher.iloc[-1]['trend_confirmed']
    current_price = latest_row['close']
    atr = latest_row['atr']

    # ----- استراتژی خرید -----
    buy_factors = set()
    buy_reasons = []

    if latest_row['rsi'] < SCALPING_SETTINGS['rsi_oversold'] and prev_row['rsi'] <= latest_row['rsi']:
        buy_factors.add('rsi')
        buy_reasons.append(f"RSI در ناحیه oversold ({latest_row['rsi']:.2f}) و در حال بهبود")

    if (prev_row['ema_short'] <= prev_row['ema_medium'] and 
        latest_row['ema_short'] > latest_row['ema_medium']):
        buy_factors.add('ema')
        buy_reasons.append(f"کراس EMA کوتاه‌مدت به بالای EMA میان‌مدت با فاصله {abs(latest_row['ema_short'] - latest_row['ema_medium']):.4f}")

    if prev_row['macd'] <= prev_row['macd_signal'] and latest_row['macd'] > latest_row['macd_signal']:
        buy_factors.add('macd')
        buy_reasons.append(f"کراس MACD به بالای خط سیگنال با اختلاف {latest_row['macd_diff']:.4f}")

    if latest_row['close'] <= latest_row['bb_lower'] * 1.01:
        buy_factors.add('bb')
        buy_reasons.append(f"قیمت نزدیک/زیر باند پایین بولینگر ({latest_row['close'] - latest_row['bb_lower']:.4f})")

    if latest_row['volume_change'] > SCALPING_SETTINGS['volume_change_threshold']:
        buy_factors.add('volume')
        buy_reasons.append(f"افزایش حجم معاملات ({latest_row['volume_change']:.2f}X)")

    if latest_row['close'] <= latest_row['support'] * 1.01:
        buy_factors.add('support')
        buy_reasons.append(f"قیمت روی حمایت ({latest_row['support']:.4f})")

    if latest_row['price_change'] > 0.003 and latest_row['close'] > latest_row['open']:
        buy_factors.add('price_action')
        buy_reasons.append(f"کندل صعودی قوی (+{latest_row['price_change']*100:.2f}%)")

    if higher_tf_trend in ['up', 'neutral']:
        buy_factors.add('higher_tf')
        buy_reasons.append(f"روند صعودی یا خنثی در تایم فریم 1 ساعته")

    # تولید سیگنال خرید
    if len(buy_reasons) >= 2:
        score = calculate_score(buy_factors, set(), atr, current_price)
        if score >= SCALPING_SETTINGS['min_score_threshold']:
            target_price = current_price + (atr * SCALPING_SETTINGS['profit_target_multiplier'])
            stop_loss = current_price - (atr * SCALPING_SETTINGS['stop_loss_multiplier'])
            risk_reward_ratio = (target_price - current_price) / (current_price - stop_loss)
            if risk_reward_ratio >= SCALPING_SETTINGS['min_risk_reward_ratio']:
                current_time = datetime.now(pytz.timezone('Asia/Tehran')).strftime("%Y-%m-%d %H:%M:%S")
                signals.append({
                    'symbol': symbol,
                    'type': 'خرید',
                    'current_price': f"{current_price:.8f}",
                    'target_price': f"{target_price:.8f}",
                    'stop_loss': f"{stop_loss:.8f}",
                    'time': current_time,
                    'reasons': "\n".join([f"✅ {reason}" for reason in buy_reasons]),
                    'score': score,
                    'status': 'active',
                    'created_at': current_time,
                    'risk_reward_ratio': risk_reward_ratio
                })

    # ----- استراتژی فروش -----
    sell_factors = set()
    sell_reasons = []

    if latest_row['rsi'] > SCALPING_SETTINGS['rsi_overbought'] and prev_row['rsi'] >= latest_row['rsi']:
        sell_factors.add('rsi')
        sell_reasons.append(f"RSI در ناحیه overbought ({latest_row['rsi']:.2f}) و در حال کاهش")

    if (prev_row['ema_short'] >= prev_row['ema_medium'] and 
        latest_row['ema_short'] < latest_row['ema_medium']):
        sell_factors.add('ema')
        sell_reasons.append(f"کراس EMA کوتاه‌مدت به پایین EMA میان‌مدت با فاصله {abs(latest_row['ema_short'] - latest_row['ema_medium']):.4f}")

    if prev_row['macd'] >= prev_row['macd_signal'] and latest_row['macd'] < latest_row['macd_signal']:
        sell_factors.add('macd')
        sell_reasons.append(f"کراس MACD به پایین خط سیگنال با اختلاف {latest_row['macd_diff']:.4f}")

    if latest_row['close'] >= latest_row['bb_upper'] * 0.99:
        sell_factors.add('bb')
        sell_reasons.append(f"قیمت نزدیک/بالای باند بالایی بولینگر ({latest_row['close'] - latest_row['bb_upper']:.4f})")

    if latest_row['close'] >= latest_row['resistance'] * 0.99:
        sell_factors.add('resistance')
        sell_reasons.append(f"قیمت روی مقاومت ({latest_row['resistance']:.4f})")

    if latest_row['price_change'] < -0.003 and latest_row['close'] < latest_row['open']:
        sell_factors.add('price_action')
        sell_reasons.append(f"کندل نزولی قوی ({latest_row['price_change']*100:.2f}%)")

    if higher_tf_trend in ['down', 'neutral']:
        sell_factors.add('higher_tf')
        sell_reasons.append(f"روند نزولی یا خنثی در تایم فریم 1 ساعته")

    # تولید سیگنال فروش
    if len(sell_reasons) >= 2:
        score = calculate_score(set(), sell_factors, atr, current_price)
        if score >= SCALPING_SETTINGS['min_score_threshold']:
            target_price = current_price - (atr * SCALPING_SETTINGS['profit_target_multiplier'])
            stop_loss = current_price + (atr * SCALPING_SETTINGS['stop_loss_multiplier'])
            risk_reward_ratio = (current_price - target_price) / (stop_loss - current_price)
            if risk_reward_ratio >= SCALPING_SETTINGS['min_risk_reward_ratio']:
                current_time = datetime.now(pytz.timezone('Asia/Tehran')).strftime("%Y-%m-%d %H:%M:%S")
                signals.append({
                    'symbol': symbol,
                    'type': 'فروش',
                    'current_price': f"{current_price:.8f}",
                    'target_price': f"{target_price:.8f}",
                    'stop_loss': f"{stop_loss:.8f}",
                    'time': current_time,
                    'reasons': "\n".join([f"✅ {reason}" for reason in sell_reasons]),
                    'score': score,
                    'status': 'active',
                    'created_at': current_time,
                    'risk_reward_ratio': risk_reward_ratio
                })

    return signals
