import math
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm

def get_us_gex_data(symbol: str):
    """
    使用 yfinance 免費獲取美股期權鏈數據，並以 Black-Scholes 模型計算 GEX、Walls 與 Flip
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
        
    # 抓取最近一期的期權到期日 (Front Month)
    exp_date = expirations[0]
    opt = tk.option_chain(exp_date)
    
    calls = opt.calls.copy()
    puts = opt.puts.copy()
    
    # 計算天數 T (以年為單位)
    today = pd.Timestamp.now()
    exp_dt = pd.to_datetime(exp_date)
    T = max((exp_dt - today).days, 1) / 365.0
    r = 0.045  # 無風險利率 4.5%
    
    def calculate_gamma(S, K, T, r, sigma):
        if sigma <= 0 or T <= 0 or S <= 0 or K <= 0:
            return 0.0
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
        return gamma

    # 計算 Calls GEX
    calls_gex = []
    for _, row in calls.iterrows():
        strike = row['strike']
        oi = row['openInterest'] if not math.isnan(row['openInterest']) else 0
        iv = row['impliedVolatility'] if not math.isnan(row['impliedVolatility']) else 0.2
        gamma = calculate_gamma(spot_price, strike, T, r, iv)
        # GEX (每股價變動 1% 時做市商的 Gamma 曝險金額)
        gex = gamma * oi * 100 * (spot_price ** 2) * 0.01
        calls_gex.append({'strike': strike, 'call_gex': gex})
        
    # 計算 Puts GEX
    puts_gex = []
    for _, row in puts.iterrows():
        strike = row['strike']
        oi = row['openInterest'] if not math.isnan(row['openInterest']) else 0
        iv = row['impliedVolatility'] if not math.isnan(row['impliedVolatility']) else 0.2
        gamma = calculate_gamma(spot_price, strike, T, r, iv)
        gex = -1 * gamma * oi * 100 * (spot_price ** 2) * 0.01
        puts_gex.append({'strike': strike, 'put_gex': gex})
        
    df_calls = pd.DataFrame(calls_gex)
    df_puts = pd.DataFrame(puts_gex)
    
    df_merged = pd.merge(df_calls, df_puts, on='strike', how='outer').fillna(0)
    df_merged['net_gex'] = df_merged['call_gex'] + df_merged['put_gex']
    
    # 尋找 Key Levels
    call_wall = df_merged.loc[df_merged['call_gex'].idxmax()]['strike']
    put_wall = df_merged.loc[df_merged['put_gex'].idxmin()]['strike']
    
    # 計算 Gamma Flip (Net GEX 符號變換點)
    df_sorted = df_merged.sort_values('strike')
    zero_crossings = df_sorted[(df_sorted['net_gex'] * df_sorted['net_gex'].shift(1)) <= 0]
    
    if not zero_crossings.empty:
        gamma_flip = zero_crossings.iloc[0]['strike']
    else:
        gamma_flip = df_sorted.iloc[(df_sorted['net_gex'].abs()).idxmin()]['strike']
        
    total_net_gex = df_merged['net_gex'].sum()
    
    return {
        "symbol": symbol,
        "spot_price": round(spot_price, 2),
        "exp_date": exp_date,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "gamma_flip": gamma_flip,
        "total_net_gex": round(total_net_gex, 2),
        "regime": "Positive Gamma" if total_net_gex > 0 else "Negative Gamma"
    }
