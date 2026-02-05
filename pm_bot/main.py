"""
Polymarket Trading Bot - Main Entry Point
Aggressive Mean-Reversion Strategy with AI Analysis
"""

import os
import sys
import time
import signal
import argparse
from datetime import datetime
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    PRIVATE_KEY, PM_API_KEY, PM_API_SECRET, PM_API_PASSPHRASE,
    FUNDER_ADDRESS, SIGNATURE_TYPE, CLOB_API, CHAIN_ID,
    POLL_INTERVAL_SECONDS, Z_SCORE_BUY_THRESHOLD, Z_SCORE_SELL_THRESHOLD,
    MAX_SPREAD_PCT, MIN_NET_EV, FEE_RATE, SLIPPAGE_ESTIMATE,
    SMA_PERIOD, PRICE_HISTORY_HOURS, validate_config
)
from pm_bot.data_client import DataClient, Market
from pm_bot.risk_manager import RiskManager
from pm_bot.math_engine import (
    calculate_mid_price, calculate_spread_pct, calculate_z_score,
    calculate_effective_cost, calculate_net_ev, calculate_expected_edge,
    should_take_trade, calculate_sma, calculate_volatility,
    calculate_kelly_criterion, calculate_rsi, get_advanced_signal,
    calculate_dynamic_position_size
)
from pm_bot.ai_analyzer import AIAnalyzer
from pm_bot.telegram_notifier import get_notifier

# Try importing py-clob-client
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import (
        OrderArgs, MarketOrderArgs, OrderType,
        OpenOrderParams, BalanceAllowanceParams, AssetType
    )
    from py_clob_client.order_builder.constants import BUY, SELL
    HAS_CLOB_CLIENT = True
except ImportError:
    HAS_CLOB_CLIENT = False
    print("⚠️ py-clob-client not installed. Install with: pip install py-clob-client")


class TradingBot:
    """Main trading bot orchestrator."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.running = False
        self.auth_client: Optional[ClobClient] = None
        
        # Initialize components
        self.data_client = DataClient()
        self.risk_manager = RiskManager()
        self.ai_analyzer = AIAnalyzer()
        self.telegram = get_notifier()
        
        # State
        self.markets_cache = []
        self.last_market_refresh = None
        self.last_ai_report = None
        self.last_daily_report = None
        self.win_streak = 0
        self.lose_streak = 0
        
        print(f"\n🤖 Polymarket Trading Bot v2.0 (Advanced Signals)")
        print(f"   Mode: {'DRY RUN' if dry_run else 'LIVE TRADING'}")
        print(f"   Features: Kelly + Bollinger + RSI + Telegram")
        print(f"   Poll Interval: {POLL_INTERVAL_SECONDS}s")
    
    def authenticate(self) -> bool:
        """Authenticate with Polymarket CLOB."""
        if self.dry_run:
            print("🔑 Dry run mode - skipping authentication")
            return True
        
        if not HAS_CLOB_CLIENT:
            print("❌ py-clob-client required for live trading")
            return False
        
        if not validate_config():
            return False
        
        try:
            print("🔑 Authenticating with Polymarket...")
            
            self.auth_client = ClobClient(
                CLOB_API,
                key=PRIVATE_KEY,
                chain_id=CHAIN_ID,
                signature_type=SIGNATURE_TYPE,
                funder=FUNDER_ADDRESS if FUNDER_ADDRESS else None
            )
            
            # Derive and set API credentials
            creds = self.auth_client.derive_api_key()
            self.auth_client.set_api_creds(creds)
            
            # Check balance
            balance = self.auth_client.get_balance_allowance(
                BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            )
            usdc_balance = int(balance['balance']) / 1e6
            
            print(f"✅ Authenticated successfully")
            print(f"💰 USDC Balance: ${usdc_balance:.2f}")
            
            # Update risk manager with actual balance
            if usdc_balance > 0:
                self.risk_manager.current_balance = usdc_balance
            
            return True
            
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return False
    
    def refresh_markets(self):
        """Refresh the list of active markets."""
        now = datetime.now()
        
        # Only refresh every 5 minutes
        if self.last_market_refresh:
            elapsed = (now - self.last_market_refresh).total_seconds()
            if elapsed < 300:  # 5 minutes
                return
        
        self.markets_cache = self.data_client.fetch_active_markets(limit=50)
        self.last_market_refresh = now
        
        print(f"🔄 Refreshed markets: {len(self.markets_cache)} candidates")
    
    def analyze_market(self, market: Market) -> dict:
        """
        Analyze a market for trading opportunity.
        
        Returns:
            Analysis dict with signal info
        """
        token_id = market.yes_token_id
        
        # Get orderbook
        book = self.data_client.fetch_orderbook(token_id)
        if not book:
            return {'valid': False, 'reason': 'No orderbook'}
        
        bid = book.best_bid
        ask = book.best_ask
        mid = book.mid_price
        spread_pct = book.spread_pct
        
        # Check spread
        if spread_pct > MAX_SPREAD_PCT:
            return {'valid': False, 'reason': f'Spread too wide: {spread_pct:.1f}%'}
        
        # Get price history
        prices = self.data_client.fetch_price_history(token_id, hours=PRICE_HISTORY_HOURS)
        if len(prices) < 5:
            return {'valid': False, 'reason': 'Insufficient price history'}
        
        # Calculate indicators
        sma = calculate_sma(prices, SMA_PERIOD)
        volatility = calculate_volatility(prices)
        z_score = calculate_z_score(mid, prices)
        rsi = calculate_rsi(prices)
        
        # Use advanced multi-indicator signal
        signal, confidence, indicators = get_advanced_signal(
            price=mid,
            prices=prices,
            z_score=z_score,
            spread_pct=spread_pct,
            max_spread=MAX_SPREAD_PCT
        )
        
        if signal == "NONE":
            return {'valid': False, 'reason': f'No signal (Z={z_score:.2f}, RSI={rsi:.0f})'}
        
        # Calculate costs and edge
        spread_decimal = spread_pct / 100
        effective_cost = calculate_effective_cost(FEE_RATE, spread_decimal, SLIPPAGE_ESTIMATE)
        
        # Determine direction for edge calculation
        direction = "BUY" if "BUY" in signal else "SELL"
        expected_edge = calculate_expected_edge(mid, sma, direction)
        
        # Calculate net EV
        net_ev = calculate_net_ev(expected_edge, effective_cost)
        
        if net_ev < MIN_NET_EV:
            return {'valid': False, 'reason': f'Net EV too low: {net_ev:.3f}'}
        
        return {
            'valid': True,
            'signal': signal,
            'confidence': confidence,
            'token_id': token_id,
            'price': ask if "BUY" in signal else bid,
            'mid': mid,
            'bid': bid,
            'ask': ask,
            'spread_pct': spread_pct,
            'z_score': z_score,
            'rsi': rsi,
            'sma': sma,
            'volatility': volatility,
            'expected_edge': expected_edge,
            'effective_cost': effective_cost,
            'net_ev': net_ev,
            'indicators': indicators
        }
    
    def execute_trade(self, market: Market, analysis: dict) -> bool:
        """Execute a trade based on analysis."""
        signal = analysis['signal']
        token_id = analysis['token_id']
        price = analysis['price']
        
        # Check risk
        can_trade, reason = self.risk_manager.can_open_position(token_id, market.question)
        if not can_trade:
            print(f"⚠️ Risk check failed: {reason}")
            return False
        
        # Calculate Kelly criterion for optimal sizing
        stats = self.ai_analyzer.calculate_stats(days=7)
        kelly = 0.05  # Default 5%
        if stats['total_trades'] >= 5 and stats['win_rate'] > 0:
            win_loss_ratio = stats.get('total_profit', 1) / max(stats.get('total_loss', 1), 0.01)
            kelly = calculate_kelly_criterion(stats['win_rate'], win_loss_ratio)
        
        # Calculate dynamic position size
        confidence = analysis.get('confidence', 0.5)
        size = calculate_dynamic_position_size(
            balance=self.risk_manager.current_balance,
            base_pct=0.05,
            win_streak=self.win_streak,
            lose_streak=self.lose_streak,
            signal_strength=confidence,
            kelly_fraction=kelly
        )
        
        if size <= 0:
            print("⚠️ Position size too small")
            return False
        
        shares = size / price
        z_score = analysis['z_score']
        rsi = analysis.get('rsi', 50)
        
        print(f"\n🎯 TRADE SIGNAL: {signal} (Confidence: {confidence:.0%})")
        print(f"   Market: {market.question[:50]}...")
        print(f"   Price: ${price:.4f}")
        print(f"   Z-Score: {z_score:.2f} | RSI: {rsi:.0f}")
        print(f"   Net EV: {analysis['net_ev']:.3f}")
        print(f"   Size: ${size:.2f} ({shares:.2f} shares)")
        
        # Send Telegram notification
        self.telegram.notify_trade_opened(
            signal=signal,
            question=market.question,
            price=price,
            size=size,
            z_score=z_score,
            rsi=rsi,
            confidence=confidence
        )
        
        # Determine trade side
        trade_side = "BUY" if "BUY" in signal else "SELL"
        
        if self.dry_run:
            print("   [DRY RUN - Not executing]")
            self.risk_manager.open_position(
                token_id=token_id,
                market_id=market.condition_id,
                question=market.question,
                side=trade_side,
                entry_price=price,
                size=size,
                shares=shares
            )
            return True
        
        # Execute real trade
        try:
            if signal == "BUY":
                order = OrderArgs(
                    token_id=token_id,
                    price=price,
                    size=shares,
                    side=BUY
                )
            else:
                order = OrderArgs(
                    token_id=token_id,
                    price=price,
                    size=shares,
                    side=SELL
                )
            
            signed_order = self.auth_client.create_order(order)
            response = self.auth_client.post_order(signed_order, OrderType.GTC)
            
            if response.get('success') or response.get('orderID'):
                print(f"✅ Order placed: {response.get('orderID', 'OK')}")
                
                # Track position
                self.risk_manager.open_position(
                    token_id=token_id,
                    market_id=market.condition_id,
                    question=market.question,
                    side=signal,
                    entry_price=price,
                    size=size,
                    shares=shares
                )
                return True
            else:
                print(f"❌ Order failed: {response}")
                return False
                
        except Exception as e:
            print(f"❌ Order execution error: {e}")
            return False
    
    def check_exits(self):
        """Check open positions for exit signals."""
        if not self.risk_manager.positions:
            return
        
        # Fetch current prices for all positions
        prices = {}
        for token_id in self.risk_manager.positions:
            mid = self.data_client.fetch_midpoint(token_id)
            if mid > 0:
                prices[token_id] = mid
        
        # Check for exits
        exits = self.risk_manager.check_positions(prices)
        
        for token_id, reason, exit_price in exits:
            position = self.risk_manager.positions.get(token_id)
            if not position:
                continue
            
            print(f"\n📉 EXIT SIGNAL: {reason}")
            print(f"   Market: {position.question[:50]}...")
            print(f"   Entry: ${position.entry_price:.4f} → Exit: ${exit_price:.4f}")
            
            if not self.dry_run and self.auth_client:
                try:
                    # Create sell order to close position
                    order = OrderArgs(
                        token_id=token_id,
                        price=exit_price,
                        size=position.shares,
                        side=SELL if position.side == "BUY" else BUY
                    )
                    signed_order = self.auth_client.create_order(order)
                    self.auth_client.post_order(signed_order, OrderType.GTC)
                except Exception as e:
                    print(f"⚠️ Exit order error: {e}")
            
            # Close in risk manager
            pnl = self.risk_manager.close_position(token_id, exit_price, reason)
            
            # Log trade
            self.ai_analyzer.log_trade(
                market_id=position.market_id,
                question=position.question,
                category=position.category,
                side=position.side,
                entry_price=position.entry_price,
                exit_price=exit_price,
                size=position.size,
                shares=position.shares,
                pnl=pnl,
                exit_reason=reason,
                entry_time=position.entry_time,
                exit_time=datetime.now()
            )
            
            # Update win/lose streaks
            if pnl > 0:
                self.win_streak += 1
                self.lose_streak = 0
            else:
                self.lose_streak += 1
                self.win_streak = 0
            
            # Send Telegram notification
            hold_time = (datetime.now() - position.entry_time).total_seconds() / 60
            self.telegram.notify_trade_closed(
                question=position.question,
                entry_price=position.entry_price,
                exit_price=exit_price,
                pnl=pnl,
                exit_reason=reason,
                hold_time_minutes=hold_time
            )
    
    def run_cycle(self):
        """Run one trading cycle."""
        # Refresh markets
        self.refresh_markets()
        
        # Check exits first
        self.check_exits()
        
        # Skip if in cooldown
        if self.risk_manager.is_in_cooldown():
            remaining = self.risk_manager.get_cooldown_remaining()
            print(f"⏳ In cooldown: {remaining}")
            return
        
        # Check if can open more positions
        if len(self.risk_manager.positions) >= 3:
            print("📊 Max positions reached, waiting for exits...")
            return
        
        # Scan markets for opportunities
        trades_made = 0
        for market in self.markets_cache:
            # Skip if already in this market
            if market.yes_token_id in self.risk_manager.positions:
                continue
            if market.no_token_id in self.risk_manager.positions:
                continue
            
            # Analyze
            analysis = self.analyze_market(market)
            
            if analysis['valid']:
                success = self.execute_trade(market, analysis)
                if success:
                    trades_made += 1
                    
                    # Only one trade per cycle to be safe
                    break
        
        if trades_made == 0:
            print(".", end="", flush=True)  # Progress indicator
    
    def print_ai_report(self):
        """Print AI analysis report."""
        now = datetime.now()
        
        # Only report every hour
        if self.last_ai_report:
            elapsed = (now - self.last_ai_report).total_seconds()
            if elapsed < 3600:  # 1 hour
                return
        
        self.last_ai_report = now
        print("\n" + self.ai_analyzer.generate_daily_report())
    
    def run(self):
        """Main trading loop."""
        print("\n" + "="*50)
        print("🚀 STARTING TRADING BOT")
        print("="*50)
        
        # Show initial status
        self.risk_manager.print_status()
        
        self.running = True
        cycle_count = 0
        
        try:
            while self.running:
                cycle_count += 1
                
                # Run cycle
                try:
                    self.run_cycle()
                except Exception as e:
                    print(f"\n⚠️ Cycle error: {e}")
                
                # Print status every 30 cycles
                if cycle_count % 30 == 0:
                    print()  # New line after dots
                    self.risk_manager.print_status()
                
                # Print AI report every hour
                if cycle_count % 360 == 0:  # 360 * 10s = 1 hour
                    self.print_ai_report()
                
                # Wait for next cycle
                time.sleep(POLL_INTERVAL_SECONDS)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down...")
        finally:
            self.running = False
            self.risk_manager.print_status()
            print("👋 Bot stopped")
    
    def stop(self):
        """Stop the trading bot."""
        self.running = False


def handle_signal(signum, frame):
    """Handle shutdown signals."""
    print("\n🛑 Received shutdown signal")
    sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Polymarket Trading Bot')
    parser.add_argument('--dry-run', action='store_true', help='Run without executing trades')
    parser.add_argument('--status', action='store_true', help='Show status and exit')
    parser.add_argument('--report', action='store_true', help='Show AI report and exit')
    parser.add_argument('--test-api', action='store_true', help='Test API connection and exit')
    
    args = parser.parse_args()
    
    # Handle signals
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Create bot
    bot = TradingBot(dry_run=args.dry_run)
    
    # Handle status command
    if args.status:
        bot.risk_manager.print_status()
        return
    
    # Handle report command
    if args.report:
        print(bot.ai_analyzer.generate_daily_report())
        return
    
    # Handle test-api command
    if args.test_api:
        if not bot.data_client.test_connection():
            print("❌ API test failed")
            sys.exit(1)
        print("✅ API connection successful")
        return
    
    # Authenticate for live trading
    if not args.dry_run:
        if not bot.authenticate():
            print("❌ Authentication required for live trading")
            print("   Use --dry-run for testing without authentication")
            sys.exit(1)
    
    # Run bot
    bot.run()


if __name__ == "__main__":
    main()
