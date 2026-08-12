import math
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm

def calculate_gamma(S, K, T, r, sigma):
    if sigma <= 0 or T <= 0 or S <= 0 or K <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
    return gamma

def get_us_gex_data(symbol: str):
    """
    使用 yfinance 獲取美股前 6 個到期日數據，加總計算全網 GEX、Walls 與 Flip
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
        
    # 取前 6 個到期日（約涵蓋未來 1 個月主力持倉）
    target_expirations = tk.options[:6]
    today = pd.Timestamp.now()
    r = 0.045  # 無風險利率 4.5%
    
    all_calls_gex = []
    all_puts_gex = []
    
    # 逐一計算每個到期日的 Gamma 並彙總
    for exp_date in target_expirations:
        try:
            opt = tk.option_chain(exp_date)
            calls = opt.calls.copy()
            puts = opt.puts.copy()
            
            # 針對當前到期日計算天數 T (年)
            exp_dt = pd.to_datetime(exp_date)
            T = max((exp_dt - today).days, 1) / 365.0
            
            # 計算 Calls GEX
            for _, row in calls.iterrows():
                strike = row['strike']
                oi = row['openInterest'] if not math.isnan(row['openInterest']) else 0
                iv = row['impliedVolatility'] if not math.isnan(row['impliedVolatility']) else 0.2
                gamma = calculate_gamma(spot_price, strike, T, r, iv)
                gex = gamma * oi * 100 * (spot_price ** 2) * 0.01
                all_calls_gex.append({'strike': strike, 'call_gex': gex})
                
            # 計算 Puts GEX
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
        
    # 按履約價 (strike) 加總所有到期日的 GEX
    df_calls = pd.DataFrame(all_calls_gex).groupby('strike', as_index=False).sum()
    df_puts = pd.DataFrame(all_puts_gex).groupby('strike', as_index=False).sum()
    
    df_merged = pd.merge(df_calls, df_puts, on='strike', how='outer').fillna(0)
    df_merged['net_gex'] = df_merged['call_gex'] + df_merged['put_gex']
    
    # 尋找 Key Levels (Call Wall / Put Wall)
    call_wall = df_merged.loc[df_merged['call_gex'].idxmax()]['strike']
    put_wall = df_merged.loc[df_merged['put_gex'].idxmin()]['strike']
    
    # 計算 Gamma Flip (Net GEX 轉折點)
    df_sorted = df_merged.sort_values('strike')
    zero_crossings = df_sorted[(df_sorted['net_gex'] * df_sorted['net_gex'].shift(1)) <= 0]
    
    if not zero_crossings.empty:
        gamma_flip = zero_crossings.iloc[0]['strike']
    else:
        gamma_flip = df_sorted.iloc[(df_sorted['net_gex'].abs()).idxmin()]['strike']
        
    total_net_gex = df_merged['net_gex'].sum()
    exp_date_display = f"{target_expirations[0]} 至 {target_expirations[-1]}"
    
    return {
        "symbol": symbol,
        "spot_price": round(spot_price, 2),
        "exp_date": exp_date_display,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "gamma_flip": gamma_flip,
        "total_net_gex": round(total_net_gex, 2),
        "regime": "Positive Gamma" if total_net_gex > 0 else "Negative Gamma"
    }
