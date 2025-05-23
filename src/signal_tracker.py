import json
import os
import requests
import pandas as pd
from datetime import datetime
import pytz
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from filelock import FileLock
from config import SIGNALS_FILE, KUCOIN_BASE_URL, KUCOIN_KLINE_ENDPOINT, PRIMARY_TIMEFRAME
from telegram_sender import send_telegram_message

def load_signals():
    """بارگذاری سیگنال‌ها از فایل JSON"""
    try:
        if os.path.exists(SIGNALS_FILE):
            with open(SIGNALS_FILE, 'r') as f:
                content = f.read()
                signals = json.loads(content) if content.strip() else []
                tehran_tz = pytz.timezone('Asia/Tehran')
                for signal in signals:
                    if 'status' not in signal or signal['status'] not in ['active', 'target_reached', 'stop_loss']:
                        signal['status'] = 'active'
                    if 'created_at' not in signal:
                        signal['created_at'] = datetime.now(tehran_tz).strftime("%Y-%m-%d %H:%M:%S")
                    if 'closed_at' not in signal:
                        signal['closed_at'] = None
                return signals
        return []
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {SIGNALS_FILE}: {e}")
        return []
    except Exception as e:
        print(f"Error loading signals: {e}")
        return []

def save_signals(signals):
    """ذخیره سیگنال‌ها در فایل JSON با قفل فایل"""
    lock = FileLock(f"{SIGNALS_FILE}.lock")
    try:
        with lock:
            os.makedirs(os.path.dirname(SIGNALS_FILE), exist_ok=True)
            with open(SIGNALS_FILE, 'w') as f:
                json.dump(signals, f, indent=2)
            print(f"Saved {len(signals)} signals to {SIGNALS_FILE}")
    except Exception as e:
        print(f"Error saving signals: {e}")
        send_telegram_message(f"❌ خطا در ذخیره سیگنال‌ها: {e}")

def fetch_kline_data(symbol, start_time, size=1000, interval=PRIMARY_TIMEFRAME):
    """دریافت داده‌های کندل از KuCoin از زمان مشخص‌شده به بعد"""
    url = f"{KUCOIN_BASE_URL}{KUCOIN_KLINE_ENDPOINT}"
    end_time = int(datetime.now(pytz.UTC).timestamp())
    interval_seconds = 1800  # 30 دقیقه
    start_timestamp = int(start_time.timestamp())
    
    params = {
        "symbol": symbol,
        "type": interval,
        "startAt": start_timestamp,
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
        df = df[["timestamp", "close", "high", "low"]]
        df = df.astype(float)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True).dt.tz_convert('Asia/Tehran')
        df = df.iloc[::-1].reset_index(drop=True)
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol} on {interval}: {e}")
        return None

def check_signal_status(signal, df):
    """بررسی وضعیت سیگنال با استفاده از داده‌های کندل از زمان created_at به بعد"""
    if df is None or df.empty:
        return False, None, None

    try:
        target_price = float(signal['target_price'])
        stop_loss = float(signal['stop_loss'])
        created_at = datetime.strptime(signal['created_at'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.timezone('Asia/Tehran'))
        
        # فیلتر کردن داده‌های کندل از زمان created_at به بعد
        df_filtered = df[df['timestamp'] >= created_at]

        if df_filtered.empty:
            return False, None, None

        for index, row in df_filtered.iterrows():
            timestamp = row['timestamp']
            high = row['high']
            low = row['low']

            if signal['type'] == 'خرید':
                if high >= target_price:
                    return True, 'target_reached', timestamp.strftime("%Y-%m-%d %H:%M:%S")
                elif low <= stop_loss:
                    return True, 'stop_loss', timestamp.strftime("%Y-%m-%d %H:%M:%S")
            elif signal['type'] == 'فروش':
                if low <= target_price:
                    return True, 'target_reached', timestamp.strftime("%Y-%m-%d %H:%M:%S")
                elif high >= stop_loss:
                    return True, 'stop_loss', timestamp.strftime("%Y-%m-%d %H:%M:%S")

        return False, None, None
    except Exception as e:
        print(f"Error checking signal status for {signal['symbol']}: {e}")
        return False, None, None

def update_signal_status():
    """به‌روزرسانی وضعیت سیگنال‌ها با بررسی کندل‌ها از زمان created_at"""
    signals = load_signals()
    if not signals:
        print("No signals to update")
        return

    updated = False
    tehran_tz = pytz.timezone('Asia/Tehran')
    for signal in signals:
        if signal['status'] != 'active':
            continue

        created_at = datetime.strptime(signal['created_at'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tehran_tz)
        df = fetch_kline_data(signal['symbol'], created_at, size=1000)
        if df is None:
            continue

        has_changed, new_status, close_time = check_signal_status(signal, df)
        if has_changed:
            signal['status'] = new_status
            signal['closed_at'] = close_time
            signal['closed_price'] = str(df[df['timestamp'] == pd.to_datetime(close_time, utc=True).tz_convert('Asia/Tehran')]['close'].iloc[0])
            updated = True
            print(f"Updated {signal['symbol']} to {new_status} at {close_time}")

    if updated:
        save_signals(signals)
        print("Signals updated successfully")
    else:
        print("No signals were updated")

def calculate_profit_loss(signal, df):
    """محاسبه درصد سود/زیان با استفاده از داده‌های کندل"""
    try:
        entry_price = float(signal.get('entry_price', signal['current_price']))
        if signal['status'] in ['target_reached', 'stop_loss'] and signal.get('closed_price'):
            close_price = float(signal['closed_price'])
        else:
            close_price = df['close'].iloc[-1] if not df.empty else entry_price

        if signal['type'] == 'خرید':
            return ((close_price - entry_price) / entry_price) * 100
        else:  # فروش
            return ((entry_price - close_price) / entry_price) * 100
    except (ValueError, TypeError) as e:
        print(f"Error calculating profit/loss for {signal['symbol']}: {e}")
        return None

def calculate_duration(created_at, closed_at):
    """محاسبه مدت‌زمان سیگنال (به ساعت)"""
    tehran_tz = pytz.timezone('Asia/Tehran')
    try:
        created = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
        if created.tzinfo is None:
            created = tehran_tz.localize(created)
        
        closed = datetime.strptime(closed_at, "%Y-%m-%d %H:%M:%S") if closed_at else datetime.now(tehran_tz)
        if closed.tzinfo is None:
            closed = tehran_tz.localize(closed)
        
        duration_hours = (closed - created).total_seconds() / 3600
        return round(duration_hours, 2)
    except (ValueError, TypeError) as e:
        print(f"Error calculating duration: {e}")
        return None

def generate_excel_report():
    """تولید گزارش Excel با شیت‌های مختلف"""
    update_signal_status()
    signals = load_signals()
    tehran_tz = pytz.timezone('Asia/Tehran')
    now_str = datetime.now(tehran_tz).strftime("%Y%m%d_%H%M%S")
    output_file = f"data/signals_report_{now_str}.xlsx"

    all_signals_data = []
    active_signals_data = []
    for signal in signals:
        created_at = datetime.strptime(signal['created_at'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tehran_tz)
        df = fetch_kline_data(signal['symbol'], created_at, size=100)
        if df is None:
            continue

        current_price = df['close'].iloc[-1]
        profit_loss = calculate_profit_loss(signal, df)
        duration = calculate_duration(signal['created_at'], signal.get('closed_at'))

        signal_row = {
            'Symbol': signal['symbol'],
            'Type': signal['type'],
            'Entry_Price': float(signal.get('entry_price', signal['current_price'])),
            'Target_Price': float(signal['target_price']),
            'Stop_Loss': float(signal['stop_loss']),
            'Created_At': signal['created_at'],
            'Status': signal['status'],
            'Closed_Price': float(signal['closed_price']) if signal.get('closed_price') else current_price,
            'Closed_At': signal.get('closed_at', ''),
            'Profit_Loss_%': round(profit_loss, 2) if profit_loss is not None else 0,
            'Duration_Hours': duration if duration is not None else 0,
            'Reasons': signal['reasons'].replace('✅ ', '').replace('\n', '; ')
        }
        all_signals_data.append(signal_row)

        if signal['status'] == 'active':
            price_change = profit_loss if profit_loss is not None else 0
            active_signals_data.append({
                'Symbol': signal['symbol'],
                'Type': signal['type'],
                'Entry_Price': float(signal.get('entry_price', signal['current_price'])),
                'Current_Price': current_price,
                'Price_Change_%': round(price_change, 2),
                'Created_At': signal['created_at'],
                'Reasons': signal['reasons'].replace('✅ ', '').replace('\n', '; ')
            })

    # محاسبه آمارها
    total_signals = len(signals)
    active_signals = len([s for s in signals if s['status'] == 'active'])
    target_reached = len([s for s in signals if s['status'] == 'target_reached'])
    stop_loss_signals = len([s for s in signals if s['status'] == 'stop_loss'])
    success_rate = (target_reached / (target_reached + stop_loss_signals) * 100) if (target_reached + stop_loss_signals) > 0 else 0
    avg_profit = pd.Series([s['Profit_Loss_%'] for s in all_signals_data]).mean()
    avg_duration = pd.Series([s['Duration_Hours'] for s in all_signals_data]).mean()

    stats_data = [
        {'Metric': 'Total Signals', 'Value': total_signals},
        {'Metric': 'Active Signals', 'Value': active_signals},
        {'Metric': 'Target Reached', 'Value': target_reached},
        {'Metric': 'Stop Loss Hit', 'Value': stop_loss_signals},
        {'Metric': 'Success Rate (%)', 'Value': round(success_rate, 2)},
        {'Metric': 'Average Profit/Loss (%)', 'Value': round(avg_profit, 2) if pd.notna(avg_profit) else 0},
        {'Metric': 'Average Duration (Hours)', 'Value': round(avg_duration, 2) if pd.notna(avg_duration) else 0}
    ]

    # ایجاد فایل Excel
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "All Signals"
    headers = ['Symbol', 'Type', 'Entry Price', 'Target Price', 'Stop Loss', 'Created At', 
               'Status', 'Closed Price', 'Closed At', 'Profit/Loss (%)', 'Duration (Hours)', 'Reasons']
    ws1.append(headers)
    for row in all_signals_data:
        ws1.append([row.get(h.replace(' ', '_'), '') for h in headers])

    ws2 = wb.create_sheet("Active Signals")
    headers_active = ['Symbol', 'Type', 'Entry Price', 'Current Price', 'Price Change (%)', 'Created At', 'Reasons']
    ws2.append(headers_active)
    for row in active_signals_data:
        ws2.append([row.get(h.replace(' ', '_'), '') for h in headers_active])

    ws3 = wb.create_sheet("Statistics")
    ws3.append(['Metric', 'Value'])
    for stat in stats_data:
        ws3.append([stat['Metric'], stat['Value']])

    # اعمال استایل
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

    # ذخیره فایل
    os.makedirs('data', exist_ok=True)
    wb.save(output_file)
    print(f"Excel report generated: {output_file}")

    # ارسال اعلان و فایل
    message = (
        f"📊 گزارش سیگنال‌ها تولید شد\n\n"
        f"🟢 سیگنال‌های فعال: {active_signals}\n"
        f"✅ سیگنال‌های موفق: {target_reached}\n"
        f"❌ سیگنال‌های ناموفق: {stop_loss_signals}\n"
        f"📈 نرخ موفقیت: {success_rate:.2f}%\n"
        f"📅 زمان گزارش: {now_str}\n"
        f"📂 فایل: {output_file}"
    )
    send_telegram_message(message)
    with open(output_file, 'rb') as f:
        files = {'document': (os.path.basename(output_file), f)}
        data = {'chat_id': os.environ.get('TELEGRAM_CHAT_ID'), 'caption': '📊 گزارش سیگنال‌ها'}
        response = requests.post(f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/sendDocument", files=files, data=data, timeout=15)
        if response.status_code == 200:
            print("Excel file sent to Telegram successfully")
        else:
            print(f"Error sending file to Telegram: {response.text}")

if __name__ == "__main__":
    import argparse
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
        send_telegram_message(f"❌ خطای سیستمی در گزارش‌دهی: {e}")