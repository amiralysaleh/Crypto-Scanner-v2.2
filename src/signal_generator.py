from datetime import datetime
import pytz
from config import SCALPING_SETTINGS

def calculate_score(buy_factors, sell_factors):
    """محاسبه امتیاز سیگنال بر اساس فاکتورها"""
    max_score = 100
    score = 0
    weight_rsi = 25
    weight_ema = 20
    weight_macd = 20
    weight_bb = 15
    weight_volume = 10
    weight_support_resistance = 10
    weight_price_action = 10
    weight_higher_tf = 10

    if 'rsi' in buy_factors or 'rsi' in sell_factors:
        score += weight_rsi
    if 'ema' in buy_factors or 'ema' in sell_factors:
        score += weight_ema
    if 'macd' in buy_factors or 'macd' in sell_factors:
        score += weight_macd
    if 'bb' in buy_factors or 'bb' in sell_factors:
        score += weight_bb
    if 'volume' in buy_factors or 'volume' in sell_factors:
        score += weight_volume
    if 'support' in buy_factors or 'resistance' in sell_factors:
        score += weight_support_resistance
    if 'price_action' in buy_factors or 'price_action' in sell_factors:
        score += weight_price_action
    if 'higher_tf' in buy_factors or 'higher_tf' in sell_factors:
        score += weight_higher_tf

    return min(score, max_score)

def generate_signals(df_primary, df_higher, symbol):
    """تولید سیگنال‌های خرید و فروش با تأیید تایم فریم بالاتر"""
    if df_primary is None or len(df_primary) < SCALPING_SETTINGS['trend_confirmation_window']:
        return []
    if df_higher is None or len(df_higher) < 2:
        return []

    signals = []
    latest_row = df_primary.iloc[-1]
    prev_row = df_primary.iloc[-2]
    higher_tf_trend = df_higher.iloc[-1]['trend_confirmed']
    current_price = latest_row['close']
    trend = latest_row['trend_confirmed']

    # ----- استراتژی خرید -----
    buy_factors = set()
    buy_reasons = []

    # RSI
    if (latest_row['rsi'] < SCALPING_SETTINGS['rsi_oversold'] and 
        prev_row['rsi'] < latest_row['rsi']):
        buy_factors.add('rsi')
        buy_reasons.append(f"RSI در ناحیه oversold ({latest_row['rsi']:.2f}) و در حال بهبود")

    # EMA کراس
    if (prev_row['ema_short'] <= prev_row['ema_medium'] and 
        latest_row['ema_short'] > latest_row['ema_medium']):
        buy_factors.add('ema')
        buy_reasons.append(f"کراس EMA کوتاه‌مدت به بالای EMA میان‌مدت")

    # MACD کراس
    if (prev_row['macd'] <= prev_row['macd_signal'] and 
        latest_row['macd'] > latest_row['macd_signal']):
        buy_factors.add('macd')
        buy_reasons.append(f"کراس MACD به بالای خط سیگنال")

    # Bollinger Bands
    if latest_row['close'] <= latest_row['bb_lower'] * 1.01:
        buy_factors.add('bb')
        buy_reasons.append(f"قیمت نزدیک/زیر باند پایین بولینگر")

    # حجم معاملات
    if latest_row['volume_change'] > SCALPING_SETTINGS['volume_change_threshold']:
        buy_factors.add('volume')
        buy_reasons.append(f"افزایش حجم ({latest_row['volume_change']:.2f}X)")

    # حمایت
    if latest_row['close'] <= latest_row['support'] * 1.01:
        buy_factors.add('support')
        buy_reasons.append(f"قیمت روی حمایت ({latest_row['support']:.4f})")

    # اکشن پرایس: کندل صعودی قوی
    if latest_row['price_change'] > 0.5 / 100 and latest_row['close'] > latest_row['open']:
        buy_factors.add('price_action')
        buy_reasons.append(f"کندل صعودی قوی (+0.5%)")

    # تأیید تایم فریم بالاتر
    if higher_tf_trend == 'up':
        buy_factors.add('higher_tf')
        buy_reasons.append(f"روند صعودی در تایم فریم 1 ساعته تأیید شد")

    # تولید سیگنال خرید
    if trend == 'up' and higher_tf_trend == 'up' and len(buy_reasons) >= 2:
        score = calculate_score(buy_factors, set())
        if score >= SCALPING_SETTINGS['min_score_threshold']:
            target_price = current_price * (1 + SCALPING_SETTINGS['profit_target_percent'] / 100)
            stop_loss = current_price * (1 - SCALPING_SETTINGS['stop_loss_percent'] / 100)
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
                'created_at': current_time
            })

    # ----- استراتژی فروش -----
    sell_factors = set()
    sell_reasons = []

    # RSI
    if (latest_row['rsi'] > SCALPING_SETTINGS['rsi_overbought'] and 
        prev_row['rsi'] > latest_row['rsi']):
        sell_factors.add('rsi')
        sell_reasons.append(f"RSI در ناحیه overbought ({latest_row['rsi']:.2f}) و در حال کاهش")

    # EMA کراس
    if (prev_row['ema_short'] >= prev_row['ema_medium'] and 
        latest_row['ema_short'] < latest_row['ema_medium']):
        sell_factors.add('ema')
        sell_reasons.append(f"کراس EMA کوتاه‌مدت به پایین EMA میان‌مدت")

    # MACD کراس
    if (prev_row['macd'] >= prev_row['macd_signal'] and 
        latest_row['macd'] < latest_row['macd_signal']):
        sell_factors.add('macd')
        sell_reasons.append(f"کراس MACD به پایین خط سیگنال")

    # Bollinger Bands
    if latest_row['close'] >= latest_row['bb_upper'] * 0.99:
        sell_factors.add('bb')
        sell_reasons.append(f"قیمت نزدیک/بالای باند بالایی بولینگر")

    # مقاومت
    if latest_row['close'] >= latest_row['resistance'] * 0.99:
        sell_factors.add('resistance')
        sell_reasons.append(f"قیمت روی مقاومت ({latest_row['resistance']:.4f})")

    # اکشن پرایس: کندل نزولی قوی
    if latest_row['price_change'] < -0.5 / 100 and latest_row['close'] < latest_row['open']:
        sell_factors.add('price_action')
        sell_reasons.append(f"کندل نزولی قوی (-0.5%)")

    # تأیید تایم فریم بالاتر
    if higher_tf_trend == 'down':
        sell_factors.add('higher_tf')
        sell_reasons.append(f"روند نزولی در تایم فریم 1 ساعته تأیید شد")

    # تولید سیگنال فروش
    if trend == 'down' and higher_tf_trend == 'down' and len(sell_reasons) >= 2:
        score = calculate_score(set(), sell_factors)
        if score >= SCALPING_SETTINGS['min_score_threshold']:
            target_price = current_price * (1 - SCALPING_SETTINGS['profit_target_percent'] / 100)
            stop_loss = current_price * (1 + SCALPING_SETTINGS['stop_loss_percent'] / 100)
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
                'created_at': current_time
            })

    return signals