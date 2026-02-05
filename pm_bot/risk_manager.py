"""
Polymarket Trading Bot - Risk Manager
Handles position sizing, exposure limits, stop/take profit, and daily loss tracking
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    MAX_TRADE_SIZE, MIN_TRADE_SIZE, MAX_POSITIONS,
    STOP_LOSS_PCT, TAKE_PROFIT_PCT, TRAILING_STOP_PCT,
    MAX_DAILY_LOSS_PCT, COOLDOWN_HOURS, INITIAL_BALANCE,
    CATEGORY_BUCKETS
)


@dataclass
class Position:
    """Represents an open position."""
    token_id: str
    market_id: str
    question: str
    category: str
    side: str  # "BUY" or "SELL"
    entry_price: float
    size: float  # Amount in USDC
    shares: float  # Number of shares
    entry_time: datetime
    highest_price: float = 0.0  # For trailing stop
    stop_loss: float = 0.0
    take_profit: float = 0.0
    
    def __post_init__(self):
        if self.highest_price == 0:
            self.highest_price = self.entry_price
        if self.stop_loss == 0:
            self.stop_loss = self.entry_price * (1 - STOP_LOSS_PCT)
        if self.take_profit == 0:
            self.take_profit = self.entry_price * (1 + TAKE_PROFIT_PCT)
    
    def update_trailing_stop(self, current_price: float) -> float:
        """Update trailing stop based on highest price."""
        if current_price > self.highest_price:
            self.highest_price = current_price
        return self.highest_price * (1 - TRAILING_STOP_PCT)
    
    def should_exit(self, current_price: float) -> Tuple[bool, str]:
        """Check if position should be exited."""
        trailing_stop = self.update_trailing_stop(current_price)
        
        # Stop loss hit
        if current_price <= self.stop_loss:
            return True, "STOP_LOSS"
        
        # Take profit hit
        if current_price >= self.take_profit:
            return True, "TAKE_PROFIT"
        
        # Trailing stop hit (only if we're in profit)
        if current_price >= self.entry_price * 1.05:  # 5% in profit
            if current_price <= trailing_stop:
                return True, "TRAILING_STOP"
        
        return False, ""
    
    def calculate_pnl(self, current_price: float) -> float:
        """Calculate current P&L."""
        if self.side == "BUY":
            return (current_price - self.entry_price) * self.shares
        else:
            return (self.entry_price - current_price) * self.shares
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            **asdict(self),
            'entry_time': self.entry_time.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Position':
        """Create position from dictionary."""
        data['entry_time'] = datetime.fromisoformat(data['entry_time'])
        return cls(**data)


class RiskManager:
    """Manages trading risk and position tracking."""
    
    def __init__(self, initial_balance: float = INITIAL_BALANCE):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.positions: Dict[str, Position] = {}  # token_id -> Position
        self.daily_pnl = 0.0
        self.daily_start_balance = initial_balance
        self.last_reset_date = datetime.now().date()
        self.cooldown_until: Optional[datetime] = None
        self.state_file = "risk_state.json"
        
        # Load saved state
        self._load_state()
    
    def _load_state(self):
        """Load state from file."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                self.current_balance = state.get('current_balance', self.initial_balance)
                self.daily_pnl = state.get('daily_pnl', 0.0)
                self.daily_start_balance = state.get('daily_start_balance', self.initial_balance)
                
                if state.get('last_reset_date'):
                    self.last_reset_date = datetime.fromisoformat(state['last_reset_date']).date()
                
                if state.get('cooldown_until'):
                    self.cooldown_until = datetime.fromisoformat(state['cooldown_until'])
                
                # Load positions
                for token_id, pos_data in state.get('positions', {}).items():
                    self.positions[token_id] = Position.from_dict(pos_data)
                
                print(f"📂 Loaded state: Balance=${self.current_balance:.2f}, {len(self.positions)} positions")
            except Exception as e:
                print(f"⚠️ Failed to load state: {e}")
    
    def _save_state(self):
        """Save state to file."""
        state = {
            'current_balance': self.current_balance,
            'daily_pnl': self.daily_pnl,
            'daily_start_balance': self.daily_start_balance,
            'last_reset_date': self.last_reset_date.isoformat(),
            'cooldown_until': self.cooldown_until.isoformat() if self.cooldown_until else None,
            'positions': {tid: pos.to_dict() for tid, pos in self.positions.items()}
        }
        
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def _reset_daily_if_needed(self):
        """Reset daily P&L if new day."""
        today = datetime.now().date()
        if today != self.last_reset_date:
            print(f"📅 New day detected. Resetting daily P&L.")
            self.daily_pnl = 0.0
            self.daily_start_balance = self.current_balance
            self.last_reset_date = today
            self._save_state()
    
    def _get_category(self, question: str) -> str:
        """Determine market category from question."""
        question_lower = question.lower()
        
        for category, keywords in CATEGORY_BUCKETS.items():
            for keyword in keywords:
                if keyword in question_lower:
                    return category
        
        return "other"
    
    def is_in_cooldown(self) -> bool:
        """Check if trading is in cooldown period."""
        if self.cooldown_until is None:
            return False
        
        if datetime.now() >= self.cooldown_until:
            self.cooldown_until = None
            self._save_state()
            return False
        
        return True
    
    def get_cooldown_remaining(self) -> str:
        """Get remaining cooldown time as string."""
        if not self.is_in_cooldown():
            return "No cooldown"
        
        remaining = self.cooldown_until - datetime.now()
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    
    def can_open_position(self, token_id: str, question: str) -> Tuple[bool, str]:
        """
        Check if a new position can be opened.
        
        Returns:
            Tuple of (can_open, reason)
        """
        self._reset_daily_if_needed()
        
        # Check cooldown
        if self.is_in_cooldown():
            return False, f"In cooldown. Remaining: {self.get_cooldown_remaining()}"
        
        # Check max positions
        if len(self.positions) >= MAX_POSITIONS:
            return False, f"Max positions reached ({MAX_POSITIONS})"
        
        # Check if already have position in this token
        if token_id in self.positions:
            return False, "Already have position in this market"
        
        # Check category correlation
        category = self._get_category(question)
        for pos in self.positions.values():
            if pos.category == category:
                return False, f"Already have position in category: {category}"
        
        # Check if balance is sufficient
        if self.current_balance < MIN_TRADE_SIZE:
            return False, f"Insufficient balance: ${self.current_balance:.2f}"
        
        return True, "OK"
    
    def calculate_position_size(self) -> float:
        """Calculate optimal position size based on current balance."""
        # Use 5% of current balance, capped by MAX/MIN
        size = self.current_balance * 0.05
        size = min(size, MAX_TRADE_SIZE)
        size = max(size, MIN_TRADE_SIZE)
        
        # Don't exceed available balance (minus some reserve)
        reserve = self.current_balance * 0.15  # Keep 15% reserve
        available = self.current_balance - reserve - self.get_total_exposure()
        
        if available < MIN_TRADE_SIZE:
            return 0.0
        
        return min(size, available)
    
    def get_total_exposure(self) -> float:
        """Get total exposure from all open positions."""
        return sum(pos.size for pos in self.positions.values())
    
    def open_position(
        self,
        token_id: str,
        market_id: str,
        question: str,
        side: str,
        entry_price: float,
        size: float,
        shares: float
    ) -> Position:
        """Open a new position."""
        category = self._get_category(question)
        
        position = Position(
            token_id=token_id,
            market_id=market_id,
            question=question,
            category=category,
            side=side,
            entry_price=entry_price,
            size=size,
            shares=shares,
            entry_time=datetime.now()
        )
        
        self.positions[token_id] = position
        self.current_balance -= size
        self._save_state()
        
        print(f"📈 Opened position: {side} {shares:.2f} shares @ ${entry_price:.4f}")
        print(f"   Market: {question[:50]}...")
        print(f"   Category: {category}")
        print(f"   Size: ${size:.2f}")
        
        return position
    
    def close_position(self, token_id: str, exit_price: float, reason: str = "MANUAL") -> float:
        """Close a position and return P&L."""
        if token_id not in self.positions:
            return 0.0
        
        position = self.positions[token_id]
        pnl = position.calculate_pnl(exit_price)
        
        # Return capital + P&L to balance
        self.current_balance += position.size + pnl
        self.daily_pnl += pnl
        
        print(f"📉 Closed position: {reason}")
        print(f"   Exit price: ${exit_price:.4f}")
        print(f"   P&L: ${pnl:+.2f}")
        
        del self.positions[token_id]
        
        # Check daily loss limit
        daily_loss_limit = self.daily_start_balance * MAX_DAILY_LOSS_PCT
        if self.daily_pnl < -daily_loss_limit:
            self.cooldown_until = datetime.now() + timedelta(hours=COOLDOWN_HOURS)
            print(f"🛑 Daily loss limit hit! Cooldown for {COOLDOWN_HOURS}h")
        
        self._save_state()
        return pnl
    
    def check_positions(self, prices: Dict[str, float]) -> List[Tuple[str, str, float]]:
        """
        Check all positions for exit signals.
        
        Args:
            prices: Dict of token_id -> current_price
        
        Returns:
            List of (token_id, exit_reason, exit_price) for positions to close
        """
        exits = []
        
        for token_id, position in self.positions.items():
            if token_id in prices:
                current_price = prices[token_id]
                should_exit, reason = position.should_exit(current_price)
                
                if should_exit:
                    exits.append((token_id, reason, current_price))
        
        return exits
    
    def get_status(self) -> dict:
        """Get current risk status."""
        self._reset_daily_if_needed()
        
        daily_loss_limit = self.daily_start_balance * MAX_DAILY_LOSS_PCT
        
        return {
            'balance': self.current_balance,
            'initial_balance': self.initial_balance,
            'total_pnl': self.current_balance - self.initial_balance,
            'total_pnl_pct': ((self.current_balance / self.initial_balance) - 1) * 100,
            'daily_pnl': self.daily_pnl,
            'daily_loss_limit': daily_loss_limit,
            'daily_loss_remaining': daily_loss_limit + self.daily_pnl,
            'open_positions': len(self.positions),
            'max_positions': MAX_POSITIONS,
            'total_exposure': self.get_total_exposure(),
            'is_cooldown': self.is_in_cooldown(),
            'cooldown_remaining': self.get_cooldown_remaining() if self.is_in_cooldown() else None
        }
    
    def print_status(self):
        """Print formatted status."""
        status = self.get_status()
        
        print("\n" + "="*50)
        print("💰 RISK MANAGER STATUS")
        print("="*50)
        print(f"Balance: ${status['balance']:.2f}")
        print(f"Total P&L: ${status['total_pnl']:+.2f} ({status['total_pnl_pct']:+.1f}%)")
        print(f"Daily P&L: ${status['daily_pnl']:+.2f} (limit: ${-status['daily_loss_limit']:.2f})")
        print(f"Positions: {status['open_positions']}/{status['max_positions']}")
        print(f"Exposure: ${status['total_exposure']:.2f}")
        
        if status['is_cooldown']:
            print(f"⚠️ COOLDOWN: {status['cooldown_remaining']}")
        
        if self.positions:
            print("\n📊 Open Positions:")
            for tid, pos in self.positions.items():
                print(f"   - {pos.question[:40]}...")
                print(f"     {pos.side} @ ${pos.entry_price:.4f} | Size: ${pos.size:.2f}")
        
        print("="*50 + "\n")


if __name__ == "__main__":
    # Test the risk manager
    rm = RiskManager(initial_balance=10.0)
    rm.print_status()
    
    # Test position opening
    can_open, reason = rm.can_open_position("test_token", "Will Bitcoin reach $100k?")
    print(f"Can open: {can_open} - {reason}")
    
    if can_open:
        size = rm.calculate_position_size()
        print(f"Position size: ${size:.2f}")
        
        # Open test position
        rm.open_position(
            token_id="test_token",
            market_id="test_market",
            question="Will Bitcoin reach $100k?",
            side="BUY",
            entry_price=0.45,
            size=size,
            shares=size / 0.45
        )
        
        rm.print_status()
        
        # Close position
        pnl = rm.close_position("test_token", 0.50, "TEST")
        print(f"Closed with P&L: ${pnl:.2f}")
        
        rm.print_status()
