import json
import os
import requests
import argparse
from datetime import datetime, timedelta
import pytz
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from filelock import FileLock
from config import SIGNALS_FILE, KUCOIN_BASE_URL, KUCOIN_KLINE_ENDPOINT, KUCOIN_TICKER_ENDPOINT
from telegram_sender import send_telegram_message

def load_signals():
    """Load signals from JSON file with proper timezone handling"""
    try:
        if os.path.exists(SIGNALS_FILE):
            with open(SIGNALS_FILE, 'r') as f:
                content = f.read()
                signals = json.loads(content) if content.strip() else []
                print(f"Loaded {len(signals)} signals from {SIGNALS_FILE}")
                tehran_tz = pytz.timezone('Asia/Tehran')
                for signal in signals:
                    # Ensure valid status
                    if 'status' not in signal or signal['status'] not in ['active', 'target_reached', 'stop_loss']:
                        print(f"Fixing invalid status for {signal.get('symbol', 'unknown')}")
                        signal['status'] = 'active'
                    # Ensure created_at is timezone-aware
                    if 'created_at' not in signal:
                        signal['created_at'] = datetime.now(tehran_tz).isoformat()
                    else:
                        try:
                            created_at = datetime.fromisoformat(signal['created_at'])
                            if created_at.tzinfo is None:
                                created_at = tehran_tz.localize(created_at)
                                signal['created_at'] = created_at.isoformat()
                        except ValueError:
                            created_at = datetime.strptime(signal['created_at'], "%Y-%m-%d %H:%M:%S")
                            created_at = tehran_tz.localize(created_at)
                            signal['created_at'] = created_at.isoformat()
                    # Handle closed_at if present
                    if 'closed_at' in signal and signal['closed_at']:
                        try:
                            closed_at = datetime.fromisoformat(signal['closed_at'])
                            if closed_at.tzinfo is None:
                                closed_at = tehran_tz.localize(closed_at)
                                signal['closed_at'] = closed_at.isoformat()
                        except ValueError:
                            try:
                                closed_at = datetime.strptime(signal['closed_at'], "%Y-%m-%d %H:%M:%S")
                                closed_at = tehran_tz.localize(closed_at)
                                signal['closed_at'] = closed_at.isoformat()
                            except ValueError:
                                signal['closed_at'] = None
                return signals
        print(f"No signals found at {SIGNALS_FILE}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {SIGNALS_FILE}: {e}")
        return []
    except Exception as e:
        print(f"Error loading signals: {e}")
        return []

def save_signals(signals):
    """Save signals to JSON file with proper timezone handling"""
    lock = FileLock(f"{SIGNALS_FILE}.lock")
    try:
        with lock:
            os.makedirs(os.path.dirname(SIGNALS_FILE), exist_ok=True)
            with open(SIGNALS_FILE, 'w') as f:
                json.dump(signals, f, indent=2)
            print(f"Saved {len(signals)} signals to {SIGNALS_FILE}")
    except Exception as e:
        print(f"Error saving signals: {e}")
        send_telegram_message(f"❌ Error saving signals: {e}")

def save_signal(signal):
    """Save a single signal with proper timezone handling"""
    tehran_tz = pytz.timezone('Asia/Tehran')
    if 'entry_price' not in signal:
        signal['entry_price'] = signal.get('current_price')
    if 'status' not in signal:
        signal['status'] = 'active'
    if 'created_at' not in signal:
        signal['created_at'] = datetime.now(tehran_tz).isoformat()
    
    signals = load_signals()
    signals.append(signal)
    save_signals(signals)
    print(f"Signal saved: {signal['symbol']} {signal['type']}")

def fetch_kline_data(symbol, start_time, end_time, interval="30min"):
    """Fetch kline data from KuCoin for a specific time range"""
    url = f"{KUCOIN_BASE_URL}{KUCOIN_KLINE_ENDPOINT}"
    params = {
        "symbol": symbol,
        "type": interval,
        "startAt": int(start_time.timestamp()),
        "endAt": int(end_time.timestamp())
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data.get('data'):
            print(f"No kline data for {symbol}: {data}")
            return None
        df = pd.DataFrame(data['data'], columns=[
            "timestamp", "open", "close", "high", "low", "volume", "turnover"
        ])
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]
        df = df.astype(float)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s").dt.tz_localize('UTC').dt.tz_convert('Asia/Tehran')
        df = df.iloc[::-1].reset_index(drop=True)
        print(f"Received {len(df)} candles for {symbol} from {start_time} to {end_time}")
        return df
    except Exception as e:
        print(f"Error fetching kline data for {symbol}: {e}")
        return None

def get_current_price(symbol):
    """Fetch current price from KuCoin"""
    url = f"{KUCOIN_BASE_URL}{KUCOIN_TICKER_ENDPOINT}"
    params = {"symbol": symbol}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        price = data.get('data', {}).get('price')
        if price:
            print(f"Current price for {symbol}: {price}")
            return float(price)
        print(f"No price data for {symbol}: {data}")
        return None
    except Exception as e:
        print(f"Error fetching price for {symbol}: {e}")
        return None

def calculate_profit_loss(signal, close_price):
    """Calculate profit/loss percentage"""
    try:
        entry_price = float(signal.get('entry_price', signal['current_price']))
        close_price = float(close_price)
        if signal['type'] == 'BUY':
            return ((close_price - entry_price) / entry_price) * 100
        else:  # SELL
            return ((entry_price - close_price) / entry_price) * 100
    except (ValueError, TypeError) as e:
        print(f"Error calculating profit/loss for {signal['symbol']}: {e}")
        return None

def calculate_duration(created_at, closed_at):
    """Calculate signal duration in hours"""
    tehran_tz = pytz.timezone('Asia/Tehran')
    try:
        created = datetime.fromisoformat(created_at)
        if created.tzinfo is None:
            created = tehran_tz.localize(created)
        
        if closed_at:
            closed = datetime.fromisoformat(closed_at)
            if closed.tzinfo is None:
                closed = tehran_tz.localize(closed)
        else:
            closed = datetime.now(tehran_tz)
        
        duration_hours = (closed - created).total_seconds() / 3600
        print(f"Duration calculated: {duration_hours:.2f} hours for created_at={created_at}, closed_at={closed_at}")
        return duration_hours
    except (ValueError, TypeError) as e:
        print(f"Error calculating duration: {e}")
        return None

def check_signal_hit(signal, df):
    """Check if signal hit target or stop-loss based on kline data"""
    try:
        target_price = float(signal['target_price'])
        stop_loss = float(signal['stop_loss'])
        signal_type = signal['type']
        created_at = datetime.fromisoformat(signal['created_at']).astimezone(pytz.timezone('Asia/Tehran'))

        for _, row in df.iterrows():
            candle_time = row['timestamp']
            if candle_time <= created_at:
                continue  # Skip candles before signal creation
            high = row['high']
            low = row['low']
            
            if signal_type == 'BUY':
                if high >= target_price:
                    return 'target_reached', str(row['close']), candle_time.isoformat()
                if low <= stop_loss:
                    return 'stop_loss', str(row['close']), candle_time.isoformat()
            elif signal_type == 'SELL':
                if low <= target_price:
                    return 'target_reached', str(row['close']), candle_time.isoformat()
                if high >= stop_loss:
                    return 'stop_loss', str(row['close']), candle_time.isoformat()
        return None, None, None
    except Exception as e:
        print(f"Error checking signal hit for {signal['symbol']}: {e}")
        return None, None, None

def update_signal_status():
    """Update signal statuses by checking historical kline data"""
    signals = load_signals()
    if not signals:
        print("No signals to update")
        return

    updated = False
    tehran_tz = pytz.timezone('Asia/Tehran')
    now = datetime.now(tehran_tz)
    
    for signal in signals:
        if signal['status'] != 'active':
            print(f"Skipping {signal['symbol']}: Already {signal['status']}")
            continue

        try:
            created_at = datetime.fromisoformat(signal['created_at']).astimezone(tehran_tz)
            # Fetch kline data from signal creation to now
            df = fetch_kline_data(signal['symbol'], created_at, now, interval="30min")
            if df is None:
                print(f"Skipping update for {signal['symbol']} due to missing kline data")
                continue

            status, closed_price, closed_at = check_signal_hit(signal, df)
            if status:
                signal['status'] = status
                signal['closed_price'] = closed_price
                signal['closed_at'] = closed_at
                updated = True
                print(f"Updated {signal['symbol']}: {status} at {closed_price} on {closed_at}")
                send_telegram_message(
                    f"📢 Signal Update for {signal['symbol']}\n"
                    f"Status: {status.replace('_', ' ').title()}\n"
                    f"Closed Price: {closed_price}\n"
                    f"Time: {closed_at}"
                )
        except Exception as e:
            print(f"Error updating {signal['symbol']}: {e}")

    if updated:
        save_signals(signals)
        print("Signals updated successfully")
    else:
        print("No signals were updated")

def send_telegram_file(file_path):
    """Send file to Telegram"""
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    if not bot_token or not chat_id:
        print("Error: Telegram credentials not set")
        return False

    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    try:
        with open(file_path, 'rb') as f:
            files = {'document': (os.path.basename(file_path), f)}
            data = {
                'chat_id': chat_id,
                'caption': '📊 Signals Report'
            }
            response = requests.post(url, files=files, data=data, timeout=15)
            if response.status_code == 200:
                print(f"File {file_path} sent to Telegram")
                return True
            else:
                print(f"Error sending file to Telegram: {response.text}")
                return False
    except Exception as e:
        print(f"Error sending file to Telegram: {e}")
        return False

def generate_excel_report():
    """Generate Excel report with multiple sheets"""
    update_signal_status()
    signals = load_signals()
    tehran_tz = pytz.timezone('Asia/Tehran')
    now_str = datetime.now(tehran_tz).strftime("%Y%m%d_%H%M%S")
    output_file = f"data/signals_report_{now_str}.xlsx"

    # Prepare data for sheets
    all_signals_data = []
    active_signals_data = []
    for signal in signals:
        current_price = get_current_price(signal['symbol']) if signal['status'] == 'active' else None
        close_price = float(signal['closed_price']) if signal.get('closed_price') else current_price
        profit_loss = calculate_profit_loss(signal, close_price) if close_price is not None else None
        duration = calculate_duration(signal['created_at'], signal.get('closed_at'))
        
        signal_row = {
            'Symbol': signal['symbol'],
            'Type': signal['type'],
            'Entry_Price': float(signal.get('entry_price', signal['current_price'])),
            'Target_Price': float(signal['target_price']),
            'Stop_Loss': float(signal['stop_loss']),
            'Created_At': signal['created_at'],
            'Status': signal['status'],
            'Closed_Price': float(signal['closed_price']) if signal.get('closed_price') else None,
            'Closed_At': signal.get('closed_at'),
            'Profit_Loss_%': round(profit_loss, 2) if profit_loss is not None else None,
            'Duration_Hours': round(duration, 2) if duration is not None else None,
            'Reasons': signal['reasons'].replace('✅ ', '').replace('\n', '; ')
        }
        all_signals_data.append(signal_row)
        
        if signal['status'] == 'active' and current_price is not None:
            price_change = ((current_price - signal_row['Entry_Price']) / signal_row['Entry_Price']) * 100
            active_signals_data.append({
                'Symbol': signal['symbol'],
                'Type': signal['type'],
                'Entry_Price': signal_row['Entry_Price'],
                'Current_Price': current_price,
                'Price_Change_%': round(price_change, 2),
                'Created_At': signal['created_at'],
                'Reasons': signal['reasons'].replace('✅ ', '').replace('\n', '; ')
            })

    # Calculate statistics
    total_signals = len(signals)
    active_signals = len([s for s in signals if s['status'] == 'active'])
    target_reached = len([s for s in signals if s['status'] == 'target_reached'])
    stop_loss_signals = len([s for s in signals if s['status'] == 'stop_loss'])
    success_rate = (target_reached / (target_reached + stop_loss_signals) * 100) if (target_reached + stop_loss_signals) > 0 else 0
    avg_profit = pd.Series([s['Profit_Loss_%'] for s in all_signals_data if s['Profit_Loss_%'] is not None]).mean()
    avg_duration = pd.Series([s['Duration_Hours'] for s in all_signals_data if s['Duration_Hours'] is not None]).mean()

    stats_data = [
        {'Metric': 'Total Signals', 'Value': total_signals},
        {'Metric': 'Active Signals', 'Value': active_signals},
        {'Metric': 'Target Reached', 'Value': target_reached},
        {'Metric': 'Stop Loss Hit', 'Value': stop_loss_signals},
        {'Metric': 'Success Rate (%)', 'Value': round(success_rate, 2)},
        {'Metric': 'Average Profit/Loss (%)', 'Value': round(avg_profit, 2) if pd.notna(avg_profit) else None},
        {'Metric': 'Average Duration (Hours)', 'Value': round(avg_duration, 2) if pd.notna(avg_duration) else None}
    ]

    # Create Excel file
    wb = Workbook()
    
    # Sheet 1: All Signals
    ws1 = wb.active
    ws1.title = "All Signals"
    headers = ['Symbol', 'Type', 'Entry Price', 'Target Price', 'Stop Loss', 'Created At', 
               'Status', 'Closed Price', 'Closed At', 'Profit/Loss (%)', 'Duration (Hours)', 'Reasons']
    ws1.append(headers)
    for row in all_signals_data:
        ws1.append([row.get(h.replace(' ', '_'), '') for h in headers])

    # Sheet 2: Active Signals
    ws2 = wb.create_sheet("Active Signals")
    headers_active = ['Symbol', 'Type', 'Entry Price', 'Current Price', 'Price Change (%)', 'Created At', 'Reasons']
    ws2.append(headers_active)
    for row in active_signals_data:
        ws2.append([row.get(h.replace(' ', '_'), '') for h in headers_active])

    # Sheet 3: Statistics
    ws3 = wb.create_sheet("Statistics")
    ws3.append(['Metric', 'Value'])
    for stat in stats_data:
        ws3.append([stat['Metric'], stat['Value']])

    # Apply styles to sheets
    for ws in [ws1, ws2, ws3]:
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                top=Side(style='thin'), bottom=Side(style='thin'))

        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column].width = adjusted_width

        ws.freeze_panes = ws['A2']

    # Save file
    os.makedirs('data', exist_ok=True)
    try:
        wb.save(output_file)
        print(f"Excel report generated: {output_file}")
    except Exception as e:
        print(f"Error saving Excel report: {e}")
        send_telegram_message(f"❌ Error generating Excel report: {e}")
        return

    # Send notification and file to Telegram
    message = (
        f"📊 Signals report generated\n\n"
        f"🟢 Active Signals: {active_signals}\n"
        f"✅ Successful Signals: {target_reached}\n"
        f"❌ Failed Signals: {stop_loss_signals}\n"
        f"📈 Success Rate: {success_rate:.2f}%\n"
        f"📅 Report Time: {now_str}\n"
        f"📂 File: {output_file}"
    )
    if send_telegram_message(message):
        print("Telegram message sent successfully")
    else:
        print("Failed to send Telegram message")

    if send_telegram_file(output_file):
        print("Excel file sent to Telegram successfully")
    else:
        print("Failed to send Excel file to Telegram")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Track and report signal status')
    parser.add_argument('--report', action='store_true', help='Generate and send a status report')
    args = parser.parse_args()

    try:
        if args.report:
            generate_excel_report()
        else:
            update_signal_status()
    except Exception as e:
        print(f"Error in main execution: {e}")
        send_telegram_message(f"❌ System error in reporting: {e}")
