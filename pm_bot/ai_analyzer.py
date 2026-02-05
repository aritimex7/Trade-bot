"""
Polymarket Trading Bot - AI Analyzer
Analyzes trade history and provides strategy optimization suggestions
Uses local analysis (no external API required for OpenClaw)
"""

import os
import csv
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TRADE_HISTORY_FILE


@dataclass
class TradeRecord:
    """Represents a single trade record."""
    timestamp: datetime
    market_id: str
    question: str
    category: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    shares: float
    pnl: float
    exit_reason: str
    hold_duration_minutes: float


class AIAnalyzer:
    """
    Analyzes trading history and provides insights.
    Designed to work with OpenClaw.ai which runs on VPS.
    """
    
    def __init__(self, history_file: str = TRADE_HISTORY_FILE):
        self.history_file = history_file
        self.trades: List[TradeRecord] = []
        self._load_history()
    
    def _load_history(self):
        """Load trade history from CSV."""
        if not os.path.exists(self.history_file):
            return
        
        try:
            with open(self.history_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        trade = TradeRecord(
                            timestamp=datetime.fromisoformat(row['timestamp']),
                            market_id=row['market_id'],
                            question=row['question'],
                            category=row['category'],
                            side=row['side'],
                            entry_price=float(row['entry_price']),
                            exit_price=float(row['exit_price']),
                            size=float(row['size']),
                            shares=float(row['shares']),
                            pnl=float(row['pnl']),
                            exit_reason=row['exit_reason'],
                            hold_duration_minutes=float(row['hold_duration_minutes'])
                        )
                        self.trades.append(trade)
                    except Exception as e:
                        continue
            
            print(f"📂 Loaded {len(self.trades)} trade records")
        except Exception as e:
            print(f"⚠️ Error loading history: {e}")
    
    def log_trade(
        self,
        market_id: str,
        question: str,
        category: str,
        side: str,
        entry_price: float,
        exit_price: float,
        size: float,
        shares: float,
        pnl: float,
        exit_reason: str,
        entry_time: datetime,
        exit_time: datetime
    ):
        """Log a trade to history."""
        hold_duration = (exit_time - entry_time).total_seconds() / 60
        
        trade = TradeRecord(
            timestamp=exit_time,
            market_id=market_id,
            question=question,
            category=category,
            side=side,
            entry_price=entry_price,
            exit_price=exit_price,
            size=size,
            shares=shares,
            pnl=pnl,
            exit_reason=exit_reason,
            hold_duration_minutes=hold_duration
        )
        
        self.trades.append(trade)
        
        # Append to CSV
        file_exists = os.path.exists(self.history_file)
        with open(self.history_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp', 'market_id', 'question', 'category', 'side',
                'entry_price', 'exit_price', 'size', 'shares', 'pnl',
                'exit_reason', 'hold_duration_minutes'
            ])
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow({
                'timestamp': trade.timestamp.isoformat(),
                'market_id': trade.market_id,
                'question': trade.question,
                'category': trade.category,
                'side': trade.side,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'size': trade.size,
                'shares': trade.shares,
                'pnl': trade.pnl,
                'exit_reason': trade.exit_reason,
                'hold_duration_minutes': trade.hold_duration_minutes
            })
        
        print(f"📝 Trade logged: {side} | P&L: ${pnl:+.2f} | {exit_reason}")
    
    def calculate_stats(self, days: int = 7) -> Dict:
        """
        Calculate trading statistics.
        
        Args:
            days: Number of days to analyze
        
        Returns:
            Dictionary with statistics
        """
        cutoff = datetime.now() - timedelta(days=days)
        recent_trades = [t for t in self.trades if t.timestamp > cutoff]
        
        if not recent_trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'expectancy': 0,
                'total_pnl': 0,
                'avg_pnl': 0,
                'best_trade': 0,
                'worst_trade': 0,
                'avg_hold_time': 0,
                'trades_per_day': 0
            }
        
        # Basic counts
        wins = [t for t in recent_trades if t.pnl > 0]
        losses = [t for t in recent_trades if t.pnl < 0]
        
        total_profit = sum(t.pnl for t in wins)
        total_loss = abs(sum(t.pnl for t in losses))
        
        # Win rate
        win_rate = len(wins) / len(recent_trades) if recent_trades else 0
        
        # Profit factor
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # Expectancy
        avg_win = total_profit / len(wins) if wins else 0
        avg_loss = total_loss / len(losses) if losses else 0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        # Other stats
        total_pnl = sum(t.pnl for t in recent_trades)
        avg_pnl = total_pnl / len(recent_trades)
        best_trade = max(t.pnl for t in recent_trades)
        worst_trade = min(t.pnl for t in recent_trades)
        avg_hold_time = sum(t.hold_duration_minutes for t in recent_trades) / len(recent_trades)
        trades_per_day = len(recent_trades) / days
        
        return {
            'total_trades': len(recent_trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'expectancy': expectancy,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'avg_hold_time': avg_hold_time,
            'trades_per_day': trades_per_day,
            'total_profit': total_profit,
            'total_loss': total_loss
        }
    
    def analyze_by_category(self) -> Dict[str, Dict]:
        """Analyze performance by market category."""
        categories = {}
        
        for trade in self.trades:
            cat = trade.category
            if cat not in categories:
                categories[cat] = {'trades': [], 'pnl': 0}
            categories[cat]['trades'].append(trade)
            categories[cat]['pnl'] += trade.pnl
        
        results = {}
        for cat, data in categories.items():
            trades = data['trades']
            wins = [t for t in trades if t.pnl > 0]
            
            results[cat] = {
                'total_trades': len(trades),
                'win_rate': len(wins) / len(trades) if trades else 0,
                'total_pnl': data['pnl'],
                'avg_pnl': data['pnl'] / len(trades) if trades else 0
            }
        
        return results
    
    def analyze_by_exit_reason(self) -> Dict[str, Dict]:
        """Analyze performance by exit reason."""
        reasons = {}
        
        for trade in self.trades:
            reason = trade.exit_reason
            if reason not in reasons:
                reasons[reason] = {'count': 0, 'pnl': 0}
            reasons[reason]['count'] += 1
            reasons[reason]['pnl'] += trade.pnl
        
        return reasons
    
    def get_optimization_suggestions(self) -> List[str]:
        """
        Generate strategy optimization suggestions based on history.
        This is the main AI analysis function.
        """
        suggestions = []
        stats = self.calculate_stats(days=7)
        
        if stats['total_trades'] < 5:
            suggestions.append("📊 Butuh lebih banyak data trade untuk analisis akurat (min 5 trades)")
            return suggestions
        
        # Win rate analysis
        if stats['win_rate'] < 0.4:
            suggestions.append(
                f"⚠️ Win rate rendah ({stats['win_rate']:.1%}). "
                "Pertimbangkan untuk menaikkan Z-Score threshold dari -1.2 ke -1.5"
            )
        elif stats['win_rate'] > 0.7:
            suggestions.append(
                f"✅ Win rate bagus ({stats['win_rate']:.1%}). "
                "Bisa coba turunkan Z-Score threshold ke -1.0 untuk lebih banyak trades"
            )
        
        # Profit factor
        if stats['profit_factor'] < 1.0:
            suggestions.append(
                f"⚠️ Profit factor < 1 ({stats['profit_factor']:.2f}). "
                "Sistem belum profitable. Pertimbangkan untuk ketatkan stop loss dari 15% ke 10%"
            )
        elif stats['profit_factor'] > 2.0:
            suggestions.append(
                f"🚀 Profit factor excellent ({stats['profit_factor']:.2f}). "
                "Bisa pertimbangkan untuk naikkan position size"
            )
        
        # Hold time analysis
        if stats['avg_hold_time'] > 120:  # > 2 hours
            suggestions.append(
                f"⏰ Avg hold time lama ({stats['avg_hold_time']:.0f} menit). "
                "Pertimbangkan untuk ketatkan take profit dari 25% ke 20%"
            )
        
        # Category analysis
        by_category = self.analyze_by_category()
        for cat, cat_stats in by_category.items():
            if cat_stats['total_trades'] >= 3:
                if cat_stats['win_rate'] < 0.3:
                    suggestions.append(
                        f"❌ Kategori '{cat}' performa buruk ({cat_stats['win_rate']:.0%} win rate). "
                        "Pertimbangkan untuk skip kategori ini"
                    )
                elif cat_stats['win_rate'] > 0.7:
                    suggestions.append(
                        f"✅ Kategori '{cat}' performa bagus ({cat_stats['win_rate']:.0%} win rate). "
                        "Fokuskan trading di kategori ini"
                    )
        
        # Exit reason analysis
        by_exit = self.analyze_by_exit_reason()
        if 'STOP_LOSS' in by_exit:
            stop_loss_count = by_exit['STOP_LOSS']['count']
            total_trades = stats['total_trades']
            stop_loss_pct = stop_loss_count / total_trades
            
            if stop_loss_pct > 0.5:
                suggestions.append(
                    f"⚠️ Stop loss terlalu sering kena ({stop_loss_pct:.0%}). "
                    "Pertimbangkan untuk perlebar stop loss atau perbaiki entry timing"
                )
        
        if not suggestions:
            suggestions.append("✅ Strategi berjalan baik! Tidak ada perubahan disarankan saat ini.")
        
        return suggestions
    
    def generate_daily_report(self) -> str:
        """Generate daily performance report."""
        stats = self.calculate_stats(days=1)
        weekly_stats = self.calculate_stats(days=7)
        suggestions = self.get_optimization_suggestions()
        
        report = []
        report.append("=" * 50)
        report.append("📊 DAILY TRADING REPORT")
        report.append(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append("=" * 50)
        
        report.append("\n📈 TODAY'S PERFORMANCE:")
        report.append(f"   Trades: {stats['total_trades']}")
        report.append(f"   P&L: ${stats['total_pnl']:+.2f}")
        report.append(f"   Win Rate: {stats['win_rate']:.1%}")
        
        report.append("\n📊 WEEKLY PERFORMANCE:")
        report.append(f"   Trades: {weekly_stats['total_trades']}")
        report.append(f"   P&L: ${weekly_stats['total_pnl']:+.2f}")
        report.append(f"   Win Rate: {weekly_stats['win_rate']:.1%}")
        report.append(f"   Profit Factor: {weekly_stats['profit_factor']:.2f}")
        report.append(f"   Expectancy: ${weekly_stats['expectancy']:+.2f}/trade")
        report.append(f"   Trades/Day: {weekly_stats['trades_per_day']:.1f}")
        
        report.append("\n🤖 AI SUGGESTIONS:")
        for suggestion in suggestions:
            report.append(f"   {suggestion}")
        
        report.append("\n" + "=" * 50)
        
        return "\n".join(report)
    
    def get_analysis_for_ai(self) -> str:
        """
        Get formatted analysis for AI/OpenClaw to process.
        Returns structured data that AI can use to make decisions.
        """
        stats = self.calculate_stats(days=7)
        by_category = self.analyze_by_category()
        by_exit = self.analyze_by_exit_reason()
        
        analysis = {
            'period': '7_days',
            'statistics': stats,
            'by_category': by_category,
            'by_exit_reason': by_exit,
            'recent_trades': [
                {
                    'question': t.question[:50],
                    'category': t.category,
                    'side': t.side,
                    'pnl': t.pnl,
                    'exit_reason': t.exit_reason,
                    'hold_minutes': t.hold_duration_minutes
                }
                for t in self.trades[-20:]  # Last 20 trades
            ]
        }
        
        return json.dumps(analysis, indent=2, default=str)


if __name__ == "__main__":
    # Test the AI analyzer
    analyzer = AIAnalyzer()
    
    # Generate sample trades for testing
    if not analyzer.trades:
        print("📝 Generating sample trades for testing...")
        
        sample_trades = [
            ("politics", "BUY", 0.45, 0.52, 0.50, 0.08),
            ("crypto", "BUY", 0.60, 0.55, 0.50, -0.04),
            ("sports", "BUY", 0.30, 0.40, 0.50, 0.17),
            ("politics", "BUY", 0.55, 0.48, 0.50, -0.06),
            ("tech", "BUY", 0.40, 0.50, 0.50, 0.13),
        ]
        
        for i, (cat, side, entry, exit, size, pnl) in enumerate(sample_trades):
            entry_time = datetime.now() - timedelta(hours=i*4)
            exit_time = entry_time + timedelta(hours=1)
            
            analyzer.log_trade(
                market_id=f"market_{i}",
                question=f"Test question for {cat}?",
                category=cat,
                side=side,
                entry_price=entry,
                exit_price=exit,
                size=size,
                shares=size/entry,
                pnl=pnl,
                exit_reason="TAKE_PROFIT" if pnl > 0 else "STOP_LOSS",
                entry_time=entry_time,
                exit_time=exit_time
            )
    
    # Print daily report
    print(analyzer.generate_daily_report())
    
    # Print suggestions
    print("\n🤖 OPTIMIZATION SUGGESTIONS:")
    for s in analyzer.get_optimization_suggestions():
        print(f"   {s}")
