import math
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime

def calculate_gamma(S, K, T, r, sigma):
    if sigma <= 0 or T <= 0 or S <= 0 or K <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
    return gamma

def get_us_gex_data(symbol: str):
    """
    獲取美股月底及下月底期權數據，修正 Call/Put Wall 為 Open Interest 基準
    """
    tk = yf.Ticker(symbol)
    
    # 1. 獲取現價
    try:
        spot_price = tk.fast_info['lastPrice']
    except Exception:
        hist = tk.history(period="1d")
        if hist.empty:
            return None
        spot_price = hist['Close'].iloc[-1]
        
    expirations = tk.options
    if not expirations:
        return None
        
    # 2. 自動鎖定本月與下個月底到期日
    now = datetime.now()
    curr_year, curr_month = now.year, now.month
    next_year, next_month = (curr_year, curr_month + 1) if curr_month < 12 else (curr_year + 1, 1)

    curr_month_exps = [e for e in expirations if pd.to_datetime(e).year == curr_year and pd.to_datetime(e).month == curr_month]
    next_month_exps = [e for e in expirations if pd.to_datetime(e).year == next_year and pd.to_datetime(e).month == next_month]

    target_expirations = []
    if curr_month_exps:
        target_expirations.append(curr_month_exps[-1])
    if next_month_exps:
        target_expirations.append(next_month_exps[-1])

    if not target_expirations:
        target_expirations = expirations[:2]

    today = pd.Timestamp.now()
    r = 0.045
    
    # 履約價過濾區間 (現價 ±35%)
    min_strike = spot_price * 0.65
    max_strike = spot_price * 1.35
    
    all_calls_list = []
    all_puts_list = []
    
    for exp_date in target_expirations:
        try:
            opt = tk.option_chain(exp_date)
            calls = opt.calls.copy()
            puts = opt.puts.copy()
            
            calls = calls[(calls['strike'] >= min_strike) & (calls['strike'] <= max_strike)]
            puts = puts[(puts['strike'] >= min_strike) & (puts['strike'] <= max_strike)]
            
            exp_dt = pd.to_datetime(exp_date)
            T = max((exp_dt - today).days, 1) / 365.0
            
            # 計算 Calls
            for _, row in calls.iterrows():
                strike = row['strike']
                oi = row['openInterest'] if not math.isnan(row['openInterest']) else 0
                iv = row['impliedVolatility'] if not math.isnan(row['impliedVolatility']) else 0.2
                gamma = calculate_gamma(spot_price, strike, T, r, iv)
                gex = gamma * oi * 100 * (spot_price ** 2) * 0.01
                all_calls_list.append({'strike': strike, 'call_oi': oi, 'call_gex': gex})
                
            # 計算 Puts
            for _, row in puts.iterrows():
                strike = row['strike']
                oi = row['openInterest'] if not math.isnan(row['openInterest']) else 0
                iv = row['impliedVolatility'] if not math.isnan(row['impliedVolatility']) else 0.2
                gamma = calculate_gamma(spot_price, strike, T, r, iv)
                gex = -1 * gamma * oi * 100 * (spot_price ** 2) * 0.01
                all_puts_list.append({'strike': strike, 'put_oi': oi, 'put_gex': gex})
                
        except Exception:
            continue
            
    if not all_calls_list or not all_puts_list:
        return None
        
    df_calls = pd.DataFrame(all_calls_list).groupby('strike', as_index=False).sum()
    df_puts = pd.DataFrame(all_puts_list).groupby('strike', as_index=False).sum()
    
    df_merged = pd.merge(df_calls, df_puts, on='strike', how='outer').fillna(0)
    df_merged['net_gex'] = df_merged['call_gex'] + df_merged['put_gex']
    
    # --- 3. 精準計算 Call Wall & Put Wall (基於未平倉量 OI) ---
    # Call Wall: 現價上方 (或包含現價) 未平倉量最大的 Call 履約價
    otm_calls = df_merged[df_merged['strike'] >= spot_price * 0.98]
    if not otm_calls.empty:
        call_wall = otm_calls.loc[otm_calls['call_oi'].idxmax()]['strike']
    else:
        call_wall = df_merged.loc[df_merged['call_oi'].idxmax()]['strike']
        
    # Put Wall: 現價下方 (或包含現價) 未平倉量最大的 Put 履約價
    otm_puts = df_merged[df_merged['strike'] <= spot_price * 1.02]
    if not otm_puts.empty:
        put_wall = otm_puts.loc[otm_puts['put_oi'].idxmax()]['strike']
    else:
        put_wall = df_merged.loc[df_merged['put_oi'].idxmax()]['strike']
    
    # --- 4. 計算 Gamma Flip (Net GEX 正負轉折點) ---
    df_sorted = df_merged.sort_values('strike')
    zero_crossings = df_sorted[(df_sorted['net_gex'] * df_sorted['net_gex'].shift(1)) <= 0]
    
    if not zero_crossings.empty:
        gamma_flip = zero_crossings.iloc[0]['strike']
    else:
        gamma_flip = df_sorted.iloc[(df_sorted['net_gex'].abs()).idxmin()]['strike']
        
    total_net_gex = df_merged['net_gex'].sum()
    exp_date_display = " & ".join(target_expirations)
    
    return {
        "symbol": symbol,
        "spot_price": round(spot_price, 2),
        "exp_date": exp_date_display,
        "call_wall": round(call_wall, 2),
        "put_wall": round(put_wall, 2),
        "gamma_flip": round(gamma_flip, 2),
        "total_net_gex": round(total_net_gex, 2),
        "regime": "Positive Gamma" if total_net_gex > 0 else "Negative Gamma"
    }
