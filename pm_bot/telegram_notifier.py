"""
Polymarket Trading Bot - Telegram Notifier
Sends trade alerts and daily reports to Telegram
"""

import os
import requests
from datetime import datetime
from typing import Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TelegramNotifier:
    """
    Send notifications to Telegram.
    
    Setup:
    1. Create a bot via @BotFather on Telegram
    2. Get the bot token
    3. Get your chat ID by messaging the bot and checking:
       https://api.telegram.org/bot<TOKEN>/getUpdates
    4. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
    """
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.bot_token and self.chat_id)
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        if not self.enabled:
            print("⚠️ Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
    
    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message to Telegram.
        
        Args:
            message: Message text (supports HTML formatting)
            parse_mode: "HTML" or "Markdown"
        
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False
        
        try:
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": parse_mode
                },
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"⚠️ Telegram send failed: {e}")
            return False
    
    def notify_trade_opened(
        self,
        signal: str,
        question: str,
        price: float,
        size: float,
        z_score: float,
        rsi: float,
        confidence: float
    ):
        """Notify when a trade is opened."""
        emoji = "🟢" if "BUY" in signal else "🔴"
        strength = "⚡" if "STRONG" in signal else ""
        
        message = f"""
{emoji}{strength} <b>TRADE OPENED</b>

<b>Signal:</b> {signal}
<b>Market:</b> {question[:50]}...
<b>Price:</b> ${price:.4f}
<b>Size:</b> ${size:.2f}

<b>Indicators:</b>
• Z-Score: {z_score:.2f}
• RSI: {rsi:.1f}
• Confidence: {confidence:.1%}

<i>⏰ {datetime.now().strftime('%H:%M:%S')}</i>
"""
        self.send_message(message.strip())
    
    def notify_trade_closed(
        self,
        question: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        exit_reason: str,
        hold_time_minutes: float
    ):
        """Notify when a trade is closed."""
        emoji = "💰" if pnl > 0 else "💸"
        pnl_pct = ((exit_price / entry_price) - 1) * 100 if entry_price > 0 else 0
        
        message = f"""
{emoji} <b>TRADE CLOSED</b>

<b>Market:</b> {question[:50]}...
<b>Entry:</b> ${entry_price:.4f}
<b>Exit:</b> ${exit_price:.4f}
<b>P&L:</b> ${pnl:+.2f} ({pnl_pct:+.1f}%)

<b>Reason:</b> {exit_reason}
<b>Duration:</b> {hold_time_minutes:.0f} min

<i>⏰ {datetime.now().strftime('%H:%M:%S')}</i>
"""
        self.send_message(message.strip())
    
    def notify_daily_summary(
        self,
        balance: float,
        daily_pnl: float,
        total_pnl: float,
        trades_today: int,
        win_rate: float,
        profit_factor: float,
        open_positions: int
    ):
        """Send daily performance summary."""
        pnl_emoji = "📈" if daily_pnl >= 0 else "📉"
        
        message = f"""
📊 <b>DAILY SUMMARY</b>
{datetime.now().strftime('%Y-%m-%d')}

💰 <b>Balance:</b> ${balance:.2f}
{pnl_emoji} <b>Today P&L:</b> ${daily_pnl:+.2f}
📈 <b>Total P&L:</b> ${total_pnl:+.2f}

📋 <b>Stats:</b>
• Trades today: {trades_today}
• Win rate: {win_rate:.1%}
• Profit factor: {profit_factor:.2f}
• Open positions: {open_positions}

<i>Bot running on VPS ✅</i>
"""
        self.send_message(message.strip())
    
    def notify_alert(self, title: str, message: str, level: str = "INFO"):
        """Send general alert."""
        emoji_map = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "SUCCESS": "✅"
        }
        emoji = emoji_map.get(level, "📢")
        
        alert = f"""
{emoji} <b>{title}</b>

{message}

<i>⏰ {datetime.now().strftime('%H:%M:%S')}</i>
"""
        self.send_message(alert.strip())
    
    def notify_cooldown_started(self, reason: str, duration_hours: int):
        """Notify when cooldown starts."""
        message = f"""
🛑 <b>TRADING PAUSED</b>

<b>Reason:</b> {reason}
<b>Duration:</b> {duration_hours} hours

Bot will resume automatically.
"""
        self.send_message(message.strip())
    
    def notify_bot_started(self, balance: float, mode: str):
        """Notify when bot starts."""
        message = f"""
🚀 <b>BOT STARTED</b>

<b>Mode:</b> {mode}
<b>Balance:</b> ${balance:.2f}

Bot is now scanning markets...
"""
        self.send_message(message.strip())
    
    def notify_bot_stopped(self, reason: str = "Manual"):
        """Notify when bot stops."""
        message = f"""
⏹️ <b>BOT STOPPED</b>

<b>Reason:</b> {reason}
<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.send_message(message.strip())


# Global notifier instance
_notifier: Optional[TelegramNotifier] = None


def get_notifier() -> TelegramNotifier:
    """Get or create global notifier instance."""
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier


if __name__ == "__main__":
    # Test the notifier
    print("🔔 Testing Telegram Notifier\n")
    
    notifier = TelegramNotifier()
    
    if not notifier.enabled:
        print("❌ Telegram not configured")
        print("   Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        print("\n   How to get these:")
        print("   1. Message @BotFather on Telegram")
        print("   2. Send /newbot and follow instructions")
        print("   3. Copy the bot token")
        print("   4. Message your bot, then visit:")
        print("      https://api.telegram.org/bot<TOKEN>/getUpdates")
        print("   5. Find your chat_id in the response")
    else:
        print("✅ Telegram configured")
        print("   Sending test message...")
        
        success = notifier.send_message(
            "🧪 <b>Test Message</b>\n\nYour Polymarket bot is configured correctly!"
        )
        
        if success:
            print("✅ Message sent!")
        else:
            print("❌ Failed to send message")
