import requests
import pandas as pd
import numpy as np
import os
import time
from datetime import datetime, timedelta
import pytz
import ta
import traceback
from config import *
from signal_generator import generate_signals
from telegram_sender import send_telegram_message
from signal_tracker import save_signal, load_signals

def fetch_kline_data(symbol, size=100, interval="30min"):
    """Fetch kline data from KuCoin with retry"""
    url = f"{KUCOIN_BASE_URL}{KUCOIN_KLINE_ENDPOINT}"
    end_time = int(time.time())
    interval_seconds = 1800 if interval == "30min" else 3600
    start_time = end_time - (size * interval_seconds)
    
    params = {"symbol": symbol, "type": interval, "startAt": start_time, "endAt": end_time}
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
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
            print(f"Attempt {attempt + 1} failed for {symbol} on {interval}: {e}")
            time.sleep(2 ** attempt)
    return None

def fetch_volume_data(symbol):
    """Fetch 24h trading volume from KuCoin"""
    url = f"{KUCOIN_BASE_URL}{KUCOIN_STATS_ENDPOINT}"
    params = {"symbol": symbol}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        volume = float(data.get('data', {}).get('volValue', 0))
        print(f"24h volume for {symbol}: {volume} USDT")
        return volume
    except Exception as e:
        print(f"Error fetching volume for {symbol}: {e}")
        return 0

def check_trend_consistency(trend_series):
    """Check trend consistency in the time window"""
    if len(trend_series) == 0:
        return 'neutral'
    if all(trend == 'up' for trend in trend_series):
        return 'up'
    if all(trend == 'down' for trend in trend_series):
        return 'down'
    return 'neutral'

def prepare_dataframe(df, timeframe=PRIMARY_TIMEFRAME):
    """Add technical indicators and price action rules"""
    if df is None or len(df) < SCALPING_SETTINGS['trend_confirmation_window']:
        return None
    try:
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

        df['atr'] = ta.volatility.AverageTrueRange(
            high=df['high'], low=df['low'], close=df['close'], window=14
        ).average_true_range()

        df['volume_change'] = df['volume'].pct_change()
        df['price_change'] = df['close'].pct_change()
        df['resistance'] = df['high'].rolling(window=10).max()
        df['support'] = df['low'].rolling(window=10).min()
        df['trend'] = np.where(df['ema_short'] > df['ema_long'], 'up', 'down')

        window = SCALPING_SETTINGS['trend_confirmation_window']
        trend_confirmed = []
        for i in range(len(df)):
            if i < window - 1:
                trend_confirmed.append('neutral')
            else:
                trend_slice = df['trend'].iloc[i - window + 1:i + 1]
                trend_confirmed.append(check_trend_consistency(trend_slice))
        df['trend_confirmed'] = trend_confirmed
        return df
    except Exception as e:
        print(f"Error preparing DataFrame for {timeframe}: {e}")
        return None

def generate_tradingview_link(symbol):
    """Generate TradingView chart link for the given symbol"""
    # Convert symbol (e.g., BTC-USDT) to TradingView format (e.g., KUCOIN:BTCUSDT)
    tradingview_symbol = symbol.replace('-', '')
    return f"https://www.tradingview.com/chart/?symbol=KUCOIN:{tradingview_symbol}"

def main():
    print("🚀 Starting cryptocurrency analysis...")
    signals_sent = 0
    tehran_tz = pytz.timezone('Asia/Tehran')
    active_signals = {s['symbol']: s for s in load_signals() if s['status'] == 'active'}

    for crypto in CRYPTOCURRENCIES:
        print(f"Analyzing {crypto}...")
        try:
            trading_symbol = KUCOIN_SUPPORTED_PAIRS.get(crypto, crypto)
            if trading_symbol != crypto:
                print(f"Using {trading_symbol} instead of {crypto}")

            volume_24h = fetch_volume_data(trading_symbol)
            if volume_24h < SCALPING_SETTINGS['min_volume_threshold']:
                print(f"Skipping {crypto} due to low 24h volume: {volume_24h}")
                continue

            if crypto in active_signals:
                try:
                    created_at = datetime.fromisoformat(active_signals[crypto]['created_at'])
                    time_diff = (datetime.now(tehran_tz) - created_at).total_seconds() / 60
                    if time_diff < SCALPING_SETTINGS['signal_cooldown_minutes']:
                        print(f"Skipping {crypto} due to active signal cooldown")
                        continue
                except ValueError:
                    # Fallback for old format
                    created_at = datetime.strptime(active_signals[crypto]['created_at'], "%Y-%m-%d %H:%M:%S")
                    created_at = tehran_tz.localize(created_at)
                    time_diff = (datetime.now(tehran_tz) - created_at).total_seconds() / 60
                    if time_diff < SCALPING_SETTINGS['signal_cooldown_minutes']:
                        print(f"Skipping {crypto} due to active signal cooldown")
                        continue

            df_primary = fetch_kline_data(trading_symbol, size=KLINE_SIZE, interval=PRIMARY_TIMEFRAME)
            if df_primary is None:
                continue

            df_higher = fetch_kline_data(trading_symbol, size=KLINE_SIZE // 2, interval=HIGHER_TIMEFRAME)
            if df_higher is None:
                continue

            prepared_df_primary = prepare_dataframe(df_primary, PRIMARY_TIMEFRAME)
            prepared_df_higher = prepare_dataframe(df_higher, HIGHER_TIMEFRAME)
            if prepared_df_primary is None or prepared_df_higher is None:
                continue

            last_row = prepared_df_primary.iloc[-1]
            signals = generate_signals(prepared_df_primary, prepared_df_higher, crypto)
            for signal in signals:
                tradingview_link = generate_tradingview_link(signal['symbol'])
                message = (
                    f"🚨 Signal {signal['type']} for {signal['symbol']}\n\n"
                    f"💰 Current Price: {signal['current_price']}\n"
                    f"🎯 Target Price: {signal['target_price']}\n"
                    f"🛑 Stop Loss: {signal['stop_loss']}\n"
                    f"📊 Signal Score: {signal['score']}\n"
                    f"📊 Risk/Reward Ratio: {signal['risk_reward_ratio']:.2f}\n\n"
                    f"📊 Reasons:\n{signal['reasons']}\n\n"
                    f"📈 View Chart: {tradingview_link}\n"
                    f"⏱️ Time: {signal['time']}"
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

        time.sleep(0.5)

    send_telegram_message(f"✅ Scan completed. {signals_sent} signals sent.", silent=True)
    print(f"Analysis complete. {signals_sent} signals sent.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fatal error: {e}")
        send_telegram_message(f"❌ System error: {e}")
