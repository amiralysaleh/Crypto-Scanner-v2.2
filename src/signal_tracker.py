import json
import os
import requests
import argparse
from datetime import datetime
import pytz
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from config import SIGNALS_FILE, KUCOIN_BASE_URL, KUCOIN_TICKER_ENDPOINT
from telegram_sender import send_telegram_message

def load_signals():
    """بارگذاری سیگنال‌ها از فایل JSON"""
    try:
        if os.path.exists(SIGNALS_FILE):
            with open(SIGNALS_FILE, 'r') as f:
                content = f.read()
                return json.loads(content) if content.strip() else []
        return []
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {SIGNALS_FILE}")
        return []
    except Exception as e:
        print(f"Error loading signals: {e}")
        return []

def save_signals(signals):
    """ذخیره سیگنال‌ها در فایل JSON"""
    try:
        os.makedirs(os.path.dirname(SIGNALS_FILE), exist_ok=True)
        with open(SIGNALS_FILE, 'w') as f:
            json.dump(signals, f, indent=2)
    except Exception as e:
        print(f"Error saving signals: {e}")

def save_signal(signal):
    """ذخیره یک سیگنال جدید"""
    if 'entry_price' not in signal:
        signal['entry_price'] = signal.get('current_price')
    signals = load_signals()
    signals.append(signal)
    save_signals(signals)
    print(f"Signal saved: {signal['symbol']} {signal['type']}")

def get_current_price(symbol):
    """دریافت قیمت فعلی از KuCoin"""
    url = f"{KUCOIN_BASE_URL}{KUCOIN_TICKER_ENDPOINT}"
    params = {"symbol": symbol}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return float(data['data']['price']) if data.get('data') and data['data'].get('price') else None
    except Exception as e:
        print(f"Error fetching price for {symbol}: {e}")
        return None

def calculate_profit_loss(signal, current_price):
    """محاسبه درصد سود/زیان"""
    try:
        entry_price = float(signal.get('entry_price', signal['current_price']))
        if signal['status'] in ['target_reached', 'stop_loss']:
            close_price = float(signal.get('closed_price', current_price))
        else:
            close_price = current_price if current_price else entry_price
        if signal['type'] == 'خرید':
            return ((close_price - entry_price) / entry_price) * 100
        else:  # فروش
            return ((entry_price - close_price) / entry_price) * 100
    except (ValueError, TypeError):
        return None

def calculate_duration(created_at, closed_at):
    """محاسبه مدت‌زمان سیگنال (به ساعت)"""
    try:
        created = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
        closed = datetime.strptime(closed_at, "%Y-%m-%d %H:%M:%S") if closed_at else datetime.now(pytz.timezone('Asia/Tehran'))
        return (closed - created).total_seconds() / 3600
    except (ValueError, TypeError):
        return None

def update_signal_status():
    """به‌روزرسانی وضعیت سیگنال‌ها"""
    signals = load_signals()
    if not signals:
        return

    updated = False
    tehran_tz = pytz.timezone('Asia/Tehran')
    for signal in signals:
        if signal['status'] != 'active':
            continue

        current_price = get_current_price(signal['symbol'])
        if current_price is None:
            continue

        target_price = float(signal['target_price'])
        stop_loss = float(signal['stop_loss'])
        now_str = datetime.now(tehran_tz).strftime("%Y-%m-%d %H:%M:%S")

        if signal['type'] == 'خرید':
            if current_price >= target_price:
                signal['status'] = 'target_reached'
                signal['closed_price'] = str(current_price)
                signal['closed_at'] = now_str
                updated = True
            elif current_price <= stop_loss:
                signal['status'] = 'stop_loss'
                signal['closed_price'] = str(current_price)
                signal['closed_at'] = now_str
                updated = True
        elif signal['type'] == 'فروش':
            if current_price <= target_price:
                signal['status'] = 'target_reached'
                signal['closed_price'] = str(current_price)
                signal['closed_at'] = now_str
                updated = True
            elif current_price >= stop_loss:
                signal['status'] = 'stop_loss'
                signal['closed_price'] = str(current_price)
                signal['closed_at'] = now_str
                updated = True

    if updated:
        save_signals(signals)
        print("Signals updated.")

def generate_excel_report():
    """تولید گزارش Excel با شیت‌های مختلف"""
    update_signal_status()
    signals = load_signals()
    tehran_tz = pytz.timezone('Asia/Tehran')
    now_str = datetime.now(tehran_tz).strftime("%Y%m%d_%H%M%S")
    output_file = f"data/signals_report_{now_str}.xlsx"

    # آماده‌سازی داده‌ها برای شیت‌ها
    all_signals_data = []
    active_signals_data = []
    for signal in signals:
        current_price = get_current_price(signal['symbol']) if signal['status'] == 'active' else None
        profit_loss = calculate_profit_loss(signal, current_price)
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
            active_signals_data.append({
                'Symbol': signal['symbol'],
                'Type': signal['type'],
                'Entry_Price': float(signal.get('entry_price', signal['current_price'])),
                'Current_Price': current_price,
                'Price_Change_%': round(profit_loss, 2) if profit_loss is not None else None,
                'Created_At': signal['created_at'],
                'Reasons': signal['reasons'].replace('✅ ', '').replace('\n', '; ')
            })

    # محاسبه آمارها
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

    # ایجاد فایل Excel
    wb = Workbook()
    
    # شیت 1: تمام سیگنال‌ها
    ws1 = wb.active
    ws1.title = "All Signals"
    headers = ['Symbol', 'Type', 'Entry Price', 'Target Price', 'Stop Loss', 'Created At', 
               'Status', 'Closed Price', 'Closed At', 'Profit/Loss (%)', 'Duration (Hours)', 'Reasons']
    ws1.append(headers)
    for row in all_signals_data:
        ws1.append([row.get(h.replace(' ', '_'), '') for h in headers])

    # شیت 2: سیگنال‌های فعال
    ws2 = wb.create_sheet("Active Signals")
    headers_active = ['Symbol', 'Type', 'Entry Price', 'Current Price', 'Price Change (%)', 'Created At', 'Reasons']
    ws2.append(headers_active)
    for row in active_signals_data:
        ws2.append([row.get(h.replace(' ', '_'), '') for h in headers_active])

    # شیت 3: آمارها
    ws3 = wb.create_sheet("Statistics")
    ws3.append(['Metric', 'Value'])
    for stat in stats_data:
        ws3.append([stat['Metric'], stat['Value']])

    # اعمال استایل به شیت‌ها
    for ws in [ws1, ws2, ws3]:
        # استایل هدر
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                                top=Side(style='thin'), bottom=Side(style='thin'))

        # تنظیم عرض ستون‌ها
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

        # فریز کردن هدر
        ws.freeze_panes = ws['A2']

    # ذخیره فایل
    os.makedirs('data', exist_ok=True)
    wb.save(output_file)
    print(f"Excel report generated: {output_file}")

    # ارسال اعلان تلگرام
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
    print("Report sent successfully")

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
        send_telegram_message(f"❌ خطای سیستمی در گزارش‌دهی: {e}")