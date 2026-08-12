"""Entry point for the GEX Alert Engine."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler

import requests
import config
from yfinance_client import get_us_gex_data

def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

def main():
    report_lines = ["📊 **每日美股 Gamma 關鍵位點簡報**\n"]
    
    for symbol in config.WATCHLIST:
        data = get_us_gex_data(symbol)
        if not data:
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
        
    full_message = "\n".join(report_lines)
    send_telegram_message(full_message)

if __name__ == "__main__":
    main()


IST = timezone(timedelta(hours=5, minutes=30))


def setup_logging() -> None:
    """Configure logging to stdout + rotating file."""
    os.makedirs(config.LOG_DIR, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Stdout handler (INFO)
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    # File handler (DEBUG)
    fh = RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Quiet noisy third-party loggers
    for name in ("httpx", "httpcore", "telegram", "apscheduler"):
        logging.getLogger(name).setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------
# Test mode
# ---------------------------------------------------------------

async def run_test_mode() -> None:
    """Run GEX engine with sample data — no Upstox, no Telegram."""
    from gex_engine import compute_gex
    from momentum import compute_momentum_score, interpret_momentum
    from signals import detect_signals
    from test_data import SAMPLE_DATA

    print("\n" + "=" * 60)
    print("  GEX ENGINE — TEST MODE (sample data)")
    print("=" * 60)

    previous_snapshots: dict = {}

    for symbol, sdata in SAMPLE_DATA.items():
        spot = sdata["spot"]
        chain = sdata["chain"]
        expiry = sdata["expiry"]

        print(f"\n{'—' * 50}")
        print(f"  {symbol}  |  Spot: {spot:,.0f}  |  Expiry: {expiry}")
        print(f"{'—' * 50}")

        # Compute GEX
        snapshot = compute_gex(chain, spot, symbol)

        print(f"\n  Regime:      {snapshot.regime}")
        print(f"  Total GEX:   {snapshot.total_gex:,.2e}")
        print(f"  Gamma Flip:  {snapshot.gamma_flip:,.0f}")
        print(f"  Put Wall:    {snapshot.put_wall:,.0f}  (Support)")
        print(f"  Call Wall:   {snapshot.call_wall:,.0f}  (Resistance)")
        print(f"  Max Gamma:   {snapshot.max_gamma_strike:,.0f}  (Pin)")
        print(f"  PCR GEX:     {snapshot.pcr_gex:.2f}")
        print(f"  Delta Flow:  {snapshot.net_delta_flow:,.0f}")

        # Momentum
        score = compute_momentum_score(snapshot)
        interp = interpret_momentum(score)
        print(f"\n  Momentum:    {score}/100 ({interp})")

        # Signals
        prev = previous_snapshots.get(symbol)
        signals = detect_signals(snapshot, prev, momentum_score=score)

        if signals:
            print(f"\n  Signals ({len(signals)}):")
            for sig in signals:
                print(f"    [{sig.priority}] {sig.type}: {sig.message}")
        else:
            print("\n  No signals detected.")

        # Print GEX by strike (top 10 by magnitude)
        print(f"\n  Top GEX Strikes:")
        top = sorted(snapshot.gex_by_strike.items(), key=lambda x: abs(x[1]), reverse=True)[:10]
        for strike, gex in top:
            bar_len = min(30, int(abs(gex) / max(abs(g) for _, g in top) * 30))
            direction = "+" if gex > 0 else "-"
            print(f"    {strike:>8,.0f} | {direction} {'#' * bar_len} ({gex:,.2e})")

        previous_snapshots[symbol] = snapshot

    print(f"\n{'=' * 60}")
    print("  Test complete.")
    print(f"{'=' * 60}\n")


# ---------------------------------------------------------------
# Production mode
# ---------------------------------------------------------------

async def run_production() -> None:
    """Start the full GEX engine: Upstox + Telegram + Scheduler."""
    from scheduler import GEXScheduler
    from store import GEXStore
    from telegram_bot import TelegramAlertBot
    from upstox_client import UpstoxClient

    # Validate env vars
    missing = []
    for var in ("UPSTOX_API_KEY", "UPSTOX_API_SECRET", "UPSTOX_ACCESS_TOKEN",
                "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        if not getattr(config, var, ""):
            missing.append(var)
    if missing:
        logger.error("Missing required env vars: %s", ", ".join(missing))
        logger.error("Copy .env.example to .env and fill in values.")
        sys.exit(1)

    # Initialize components
    upstox = UpstoxClient()
    store = GEXStore()
    store.open()
    bot = TelegramAlertBot()

    # Wire cross-references
    bot.store = store
    bot.upstox = upstox

    # Build and start Telegram bot
    bot.build()
    await bot.start_polling()

    # Test Upstox connection
    upstox_ok = await upstox.health_check()
    if upstox_ok:
        logger.info("Upstox connection verified")
        await bot.send("\U0001f7e2 <b>GEX Engine Starting...</b>\nUpstox: \u2705")
    else:
        logger.warning("Upstox connection failed at startup")
        await bot.send(
            "\u274c <b>GEX Engine Starting...</b>\n"
            "Upstox connection failed. Use /token to update.\n"
            "Bot commands are active."
        )

    # Start scheduler (jobs guard themselves if market is closed)
    scheduler = GEXScheduler(upstox, store, bot)
    scheduler.start()

    # Keep alive
    stop_event = asyncio.Event()

    def _signal_handler(*_: object) -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    logger.info("GEX Engine running. Press Ctrl+C to stop.")
    await stop_event.wait()

    # Cleanup
    logger.info("Shutting down...")
    scheduler.stop()
    await bot.stop()
    await upstox.close()
    store.close()
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------
# CLI
# ---------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="NSE GEX Signal Engine")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run with sample data (no Upstox, no Telegram)",
    )
    parser.add_argument(
        "--auth",
        action="store_true",
        help="Print Upstox auth URL and exit",
    )
    args = parser.parse_args()

    setup_logging()

    if args.auth:
        from upstox_client import UpstoxClient
        client = UpstoxClient()
        print(f"\nOpen this URL in your browser to authorize:\n\n{client.get_auth_url()}\n")
        return

    if args.test:
        asyncio.run(run_test_mode())
    else:
        asyncio.run(run_production())


if __name__ == "__main__":
    main()
