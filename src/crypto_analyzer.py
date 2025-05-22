import requests
import pandas as pd
import numpy as np
import os
import time
from datetime import datetime
import pytz
import ta
import traceback
from config import *
from signal_generator import generate_signals
from telegram_sender import send_telegram_message
from signal_tracker import save_signal

def fetch_kline_data(symbol, size=100, interval="30min"):
    """دریافت داده‌های کندل از KuCoin"""
    url = f"{KUCOIN_BASE_URL}{KUCOIN_KLINE_ENDPOINT}"
    end_time = int(time.time())
    interval_seconds = 1800 if interval == "30min" else 3600
    start_time = end_time - (size * interval_seconds)
    
    params = {
        "symbol": symbol,
        "type": interval,
        "startAt": start_time,
        "endAt": end_time
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if not data.get('data'):
            print(f"Error fetching data for {symbol} on {interval}: {data}")
            return None

        df = pd.DataFrame(data['data'], columns=[
            "timestamp", "open", "close", "high", "low", "volume", "turnover"
        ])
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        df = df.astype(float)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
        df = df.iloc[::-1].reset_index(drop=True)
        print(f"Received {len(df)} candles for {symbol} on {interval}")
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol} on {interval}: {e}")
        print(traceback.format_exc())
        return None

def check_trend_consistency(trend_series):
    """بررسی یکنواختی روند در پنجره زمانی"""
    if len(trend_series) == 0:
        return 'neutral'
    if all(trend == 'up' for trend in trend_series):
        return 'up'
    if all(trend == 'down' for trend in trend_series):
        return 'down'
    return 'neutral'

def prepare_dataframe(df, timeframe=PRIMARY_TIMEFRAME):
    """اضافه کردن اندیکاتورهای تکنیکال و قواعد اکشن پرایس"""
    if df is None or len(df) < SCALPING_SETTINGS['trend_confirmation_window']:
        return None

    try:
        # اندیکاتورهای تکنیکال
        df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=SCALPING_SETTINGS['rsi_period']).rsi()
        df['ema_short'] = ta.trend.ema_indicator(df['close'], window=SCALPING_SETTINGS['ema_short'])
        df['ema_medium'] = ta.trend.ema_indicator(df['close'], window=SCALPING_SETTINGS['ema_medium'])
        df['ema_long'] = ta.trend.ema_indicator(df['close'], window=SCALPING_SETTINGS['ema_long'])

        macd = ta.trend.MACD(df['close'], 
                           window_fast=SCALPING_SETTINGS['macd_fast'],
                           window_slow=SCALPING_SETTINGS['macd_slow'],
                           window_sign=SCALPING_SETTINGS['macd_signal'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()

        bollinger = ta.volatility.BollingerBands(df['close'],
                                              window=SCALPING_SETTINGS['bb_period'],
                                              window_dev=SCALPING_SETTINGS['bb_std'])
        df['bb_upper'] = bollinger.bollinger_hband()
        df['bb_middle'] = bollinger.bollinger_mavg()
        df['bb_lower'] = bollinger.bollinger_lband()

        # اکشن پرایس و حجم
        df['volume_change'] = df['volume'].pct_change()
        df['price_change'] = df['close'].pct_change()
        df['resistance'] = df['high'].rolling(window=10).max()
        df['support'] = df['low'].rolling(window=10).min()

        # شناسایی روند در تایم فریم
        df['trend'] = np.where(df['ema_short'] > df['ema_long'], 'up', 'down')
        
        # محاسبه روند تأیید شده
        if timeframe == PRIMARY_TIMEFRAME:
            window = SCALPING_SETTINGS['trend_confirmation_window']
            trend_confirmed = []
            for i in range(len(df)):
                if i < window - 1:
                    trend_confirmed.append('neutral')
                else:
                    trend_slice = df['trend'].iloc[i - window + 1:i + 1]
                    trend_confirmed.append(check_trend_consistency(trend_slice))
            df['trend_confirmed'] = trend_confirmed
        else:
            df['trend_confirmed'] = df['trend']

        return df
    except Exception as e:
        print(f"Error preparing DataFrame for {timeframe}: {e}")
        print(traceback.format_exc())
        return None

def main():
    print("🚀 Starting cryptocurrency analysis...")
    signals_sent = 0

    for crypto in CRYPTOCURRENCIES:
        print(f"Analyzing {crypto}...")
        try:
            trading_symbol = KUCOIN_SUPPORTED_PAIRS.get(crypto, crypto)
            if trading_symbol != crypto:
                print(f"Using {trading_symbol} instead of {crypto}")

            # دریافت داده‌های تایم فریم اصلی (30 دقیقه)
            df_primary = fetch_kline_data(trading_symbol, size=KLINE_SIZE, interval=PRIMARY_TIMEFRAME)
            if df_primary is None:
                continue

            # دریافت داده‌های تایم فریم بالاتر (1 ساعت)
            df_higher = fetch_kline_data(trading_symbol, size=KLINE_SIZE // 2, interval=HIGHER_TIMEFRAME)
            if df_higher is None:
                continue

            # آماده‌سازی دیتافریم‌ها
            prepared_df_primary = prepare_dataframe(df_primary, PRIMARY_TIMEFRAME)
            prepared_df_higher = prepare_dataframe(df_higher, HIGHER_TIMEFRAME)
            if prepared_df_primary is None or prepared_df_higher is None:
                continue

            last_row = prepared_df_primary.iloc[-1]
            print(f"Last RSI: {last_row['rsi']:.2f}, EMA Short: {last_row['ema_short']:.2f}, "
                  f"MACD: {last_row['macd']:.6f}, Trend: {last_row['trend_confirmed']}, "
                  f"Higher TF Trend: {prepared_df_higher.iloc[-1]['trend_confirmed']}")

            # تولید سیگنال با تأیید از تایم فریم بالاتر
            signals = generate_signals(prepared_df_primary, prepared_df_higher, crypto)
            for signal in signals:
                message = (
                    f"🚨 سیگنال {signal['type']} برای {signal['symbol']}\n\n"
                    f"💰 قیمت فعلی: {signal['current_price']}\n"
                    f"🎯 قیمت هدف: {signal['target_price']}\n"
                    f"🛑 حد ضرر: {signal['stop_loss']}\n"
                    f"📊 امتیاز سیگنال: {signal['score']}\n\n"
                    f"📊 دلایل سیگنال:\n{signal['reasons']}\n\n"
                    f"⏱️ زمان: {signal['time']}"
                )
                if send_telegram_message(message):
                    signals_sent += 1
                    save_signal(signal)
                    print(f"Signal sent and saved for {crypto}: {signal['type']}")
                else:
                    print(f"Failed to send signal for {crypto}")

        except Exception as e:
            print(f"Error during analysis of {crypto}: {e}")
            print(traceback.format_exc())

        time.sleep(1)

    send_telegram_message(f"✅ اسکن تکمیل شد. {signals_sent} سیگنال ارسال شد.")
    print(f"Analysis complete. {signals_sent} signals sent.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fatal error: {e}")
        send_telegram_message(f"❌ خطای سیستمی: {e}")