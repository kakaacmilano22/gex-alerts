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
    自動鎖定「本月底」及「下個月底」最後一個期權到期日並計算 GEX
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
        
    # 2. 自動判斷本月與下個月的年份及月份
    now = datetime.now()
    curr_year, curr_month = now.year, now.month
    next_year, next_month = (curr_year, curr_month + 1) if curr_month < 12 else (curr_year + 1, 1)

    # 取出本月及下個月的所有到期日，並選取「最後一個」（即月底/月結日）
    curr_month_exps = [e for e in expirations if pd.to_datetime(e).year == curr_year and pd.to_datetime(e).month == curr_month]
    next_month_exps = [e for e in expirations if pd.to_datetime(e).year == next_year and pd.to_datetime(e).month == next_month]

    target_expirations = []
    if curr_month_exps:
        target_expirations.append(curr_month_exps[-1])  # 本月底到期日
    if next_month_exps:
        target_expirations.append(next_month_exps[-1])  # 下個月底到期日

    if not target_expirations:
        target_expirations = expirations[:2]

    today = pd.Timestamp.now()
    r = 0.045  # 無風險利率 4.5%
    
    # 履約價過濾區間 (現價 ±30%)
    min_strike = spot_price * 0.70
    max_strike = spot_price * 1.30
    
    all_calls_gex = []
    all_puts_gex = []
    
    for exp_date in target_expirations:
        try:
            opt = tk.option_chain(exp_date)
            calls = opt.calls.copy()
            puts = opt.puts.copy()
            
            calls = calls[(calls['strike'] >= min_strike) & (calls['strike'] <= max_strike)]
            puts = puts[(puts['strike'] >= min_strike) & (puts['strike'] <= max_strike)]
            
            exp_dt = pd.to_datetime(exp_date)
            T = max((exp_dt - today).days, 1) / 365.0
            
            for _, row in calls.iterrows():
                strike = row['strike']
                oi = row['openInterest'] if not math.isnan(row['openInterest']) else 0
                iv = row['impliedVolatility'] if not math.isnan(row['impliedVolatility']) else 0.2
                gamma = calculate_gamma(spot_price, strike, T, r, iv)
                gex = gamma * oi * 100 * (spot_price ** 2) * 0.01
                all_calls_gex.append({'strike': strike, 'call_gex': gex})
                
            for _, row in puts.iterrows():
                strike = row['strike']
                oi = row['openInterest'] if not math.isnan(row['openInterest']) else 0
                iv = row['impliedVolatility'] if not math.isnan(row['impliedVolatility']) else 0.2
                gamma = calculate_gamma(spot_price, strike, T, r, iv)
                gex = -1 * gamma * oi * 100 * (spot_price ** 2) * 0.01
                all_puts_gex.append({'strike': strike, 'put_gex': gex})
                
        except Exception:
            continue
            
    if not all_calls_gex or not all_puts_gex:
        return None
        
    df_calls = pd.DataFrame(all_calls_gex).groupby('strike', as_index=False).sum()
    df_puts = pd.DataFrame(all_puts_gex).groupby('strike', as_index=False).sum()
    
    df_merged = pd.merge(df_calls, df_puts, on='strike', how='outer').fillna(0)
    df_merged['net_gex'] = df_merged['call_gex'] + df_merged['put_gex']
    
    call_wall = df_merged.loc[df_merged['call_gex'].idxmax()]['strike']
    put_wall = df_merged.loc[df_merged['put_gex'].idxmin()]['strike']
    
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
