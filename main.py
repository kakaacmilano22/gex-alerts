import os
import requests
import config
from yfinance_client import get_us_gex_data

def send_telegram_message(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN") or getattr(config, "TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or getattr(config, "TELEGRAM_CHAT_ID", "")
    
    if not token or not chat_id:
        print("❌ Error: 找不到 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    res = requests.post(url, json=payload)
    if res.status_code == 200:
        print("✅ Telegram 訊息發送成功！")
    else:
        print(f"❌ Telegram 發送失敗: {res.text}")

def main():
    watchlist = getattr(config, "WATCHLIST", ["GOOG", "TQQQ", "NVDA", "AAPL"])
    report_lines = ["📊 **每日美股 Gamma 關鍵位點簡報**\n"]
    
    for symbol in watchlist:
        try:
            print(f"正在計算 {symbol}...")
            data = get_us_gex_data(symbol)
            if not data:
                print(f"⚠️ 無法取得 {symbol} 數據")
                continue
                
            status_icon = "🟢" if "Positive" in data['regime'] else "🔴"
            report_lines.append(
                f"**【{data['symbol']}】** 現價: `${data['spot_price']}`\n"
                f"• Regime: {status_icon} {data['regime']}\n"
                f"• Gamma Flip: `${data['gamma_flip']}`\n"
                f"• Call Wall (阻力): `${data['call_wall']}`\n"
                f"• Put Wall (支撐): `${data['put_wall']}`\n"
                f"• 到期日: `{data['exp_date']}`\n"
            )
        except Exception as e:
            print(f"❌ 處理 {symbol} 時發生錯誤: {e}")
        
    if len(report_lines) > 1:
        full_message = "\n".join(report_lines)
        send_telegram_message(full_message)
    else:
        print("⚠️ 未能成功計算任何股票的 Gamma 數據。")

if __name__ == "__main__":
    main()
