"""
Polymarket Trading Bot - Math Engine
Contains all trading calculations and formulas
"""

import numpy as np
from typing import List, Optional, Tuple


def calculate_mid_price(bid: float, ask: float) -> float:
    """
    Calculate the mid price between bid and ask.
    
    Formula: mid = (bid + ask) / 2
    
    Args:
        bid: Best bid price
        ask: Best ask price
    
    Returns:
        Mid price
    """
    if bid <= 0 or ask <= 0:
        return 0.0
    return (bid + ask) / 2


def calculate_spread_pct(bid: float, ask: float) -> float:
    """
    Calculate the spread as a percentage of mid price.
    
    Formula: spread_pct = ((ask - bid) / mid) * 100
    
    Args:
        bid: Best bid price
        ask: Best ask price
    
    Returns:
        Spread percentage
    """
    mid = calculate_mid_price(bid, ask)
    if mid <= 0:
        return float('inf')
    return ((ask - bid) / mid) * 100


def calculate_effective_cost(fee: float, spread: float, slippage: float) -> float:
    """
    Calculate the effective cost of a trade.
    
    Formula: effective_cost = fee + (0.5 * spread) + slippage
    
    Args:
        fee: Trading fee (as decimal, e.g., 0.002 for 0.2%)
        spread: Bid-ask spread (as decimal)
        slippage: Expected slippage (as decimal)
    
    Returns:
        Total effective cost as decimal
    """
    return fee + (0.5 * spread) + slippage


def calculate_net_ev(expected_edge: float, estimated_costs: float) -> float:
    """
    Calculate Net Expected Value.
    
    Formula: net_ev = expected_gross_edge - estimated_costs
    
    Args:
        expected_edge: Expected gross edge from the trade
        estimated_costs: Total estimated costs
    
    Returns:
        Net expected value (positive = profitable trade)
    """
    return expected_edge - estimated_costs


def calculate_z_score(last_price: float, prices: List[float]) -> float:
    """
    Calculate Z-Score for mean reversion signal.
    
    Formula: z_score = (last_price - mean) / std_dev
    
    Buy signal: Z < -1.2 (oversold)
    Sell signal: Z > +1.2 (overbought)
    
    Args:
        last_price: Current/last price
        prices: Historical prices list
    
    Returns:
        Z-Score value
    """
    if len(prices) < 2:
        return 0.0
    
    mean = np.mean(prices)
    std_dev = np.std(prices)
    
    if std_dev == 0:
        return 0.0
    
    return (last_price - mean) / std_dev


def calculate_sma(prices: List[float], period: int = 20) -> float:
    """
    Calculate Simple Moving Average.
    
    Args:
        prices: List of historical prices
        period: SMA period (default 20)
    
    Returns:
        SMA value
    """
    if len(prices) < period:
        return np.mean(prices) if prices else 0.0
    
    return np.mean(prices[-period:])


def calculate_volatility(prices: List[float], period: int = 20) -> float:
    """
    Calculate volatility (standard deviation) of prices.
    
    Args:
        prices: List of historical prices
        period: Calculation period
    
    Returns:
        Volatility (sigma)
    """
    if len(prices) < 2:
        return 0.0
    
    relevant_prices = prices[-period:] if len(prices) >= period else prices
    return np.std(relevant_prices)


def calculate_position_size(
    balance: float,
    max_trade_pct: float = 0.05,
    max_amount: float = 0.50,
    min_amount: float = 0.30
) -> float:
    """
    Calculate optimal position size.
    
    Args:
        balance: Current balance
        max_trade_pct: Max percentage of balance per trade
        max_amount: Maximum trade amount
        min_amount: Minimum trade amount
    
    Returns:
        Position size in USDC
    """
    size = balance * max_trade_pct
    size = min(size, max_amount)
    size = max(size, min_amount)
    
    # Don't trade if balance too low
    if balance < min_amount:
        return 0.0
    
    return round(size, 2)


def calculate_expected_edge(
    current_price: float,
    fair_value: float,
    direction: str = "BUY"
) -> float:
    """
    Calculate expected edge based on deviation from fair value.
    
    Args:
        current_price: Current market price
        fair_value: Estimated fair value (e.g., SMA)
        direction: "BUY" or "SELL"
    
    Returns:
        Expected edge as decimal
    """
    if direction == "BUY":
        # Buying below fair value = positive edge
        return (fair_value - current_price) / fair_value if fair_value > 0 else 0.0
    else:
        # Selling above fair value = positive edge
        return (current_price - fair_value) / fair_value if fair_value > 0 else 0.0


def should_take_trade(
    z_score: float,
    spread_pct: float,
    net_ev: float,
    z_threshold: float = -1.2,
    max_spread: float = 5.0,
    min_ev: float = 0.01
) -> Tuple[bool, str]:
    """
    Determine if a trade signal is valid.
    
    Args:
        z_score: Current Z-Score
        spread_pct: Current spread percentage
        net_ev: Net expected value
        z_threshold: Z-Score threshold for buy signal
        max_spread: Maximum allowed spread
        min_ev: Minimum required edge
    
    Returns:
        Tuple of (should_trade, signal_type)
        signal_type: "BUY", "SELL", or "NONE"
    """
    # Check spread first
    if spread_pct > max_spread:
        return False, "NONE"
    
    # Check net EV
    if net_ev < min_ev:
        return False, "NONE"
    
    # Check Z-Score for signals
    if z_score < z_threshold:
        return True, "BUY"
    elif z_score > abs(z_threshold):
        return True, "SELL"
    
    return False, "NONE"


def calculate_stop_loss_price(entry_price: float, stop_loss_pct: float = 0.15) -> float:
    """
    Calculate stop loss price.
    
    Args:
        entry_price: Entry price
        stop_loss_pct: Stop loss percentage
    
    Returns:
        Stop loss trigger price
    """
    return entry_price * (1 - stop_loss_pct)


def calculate_take_profit_price(entry_price: float, take_profit_pct: float = 0.25) -> float:
    """
    Calculate take profit price.
    
    Args:
        entry_price: Entry price
        take_profit_pct: Take profit percentage
    
    Returns:
        Take profit trigger price
    """
    return entry_price * (1 + take_profit_pct)


def calculate_trailing_stop(
    highest_price: float,
    trailing_pct: float = 0.10
) -> float:
    """
    Calculate trailing stop price.
    
    Args:
        highest_price: Highest price since entry
        trailing_pct: Trailing stop percentage
    
    Returns:
        Trailing stop trigger price
    """
    return highest_price * (1 - trailing_pct)


def calculate_profit_factor(profits: List[float], losses: List[float]) -> float:
    """
    Calculate Profit Factor.
    
    Formula: profit_factor = sum(profits) / sum(losses)
    
    Args:
        profits: List of profitable trades (positive values)
        losses: List of losing trades (positive values, absolute)
    
    Returns:
        Profit factor (>1 = profitable system)
    """
    total_profit = sum(profits) if profits else 0
    total_loss = sum(losses) if losses else 1  # Avoid division by zero
    
    if total_loss == 0:
        return float('inf') if total_profit > 0 else 0.0
    
    return total_profit / total_loss


def calculate_expectancy(
    win_rate: float,
    avg_win: float,
    avg_loss: float
) -> float:
    """
    Calculate trading expectancy.
    
    Formula: expectancy = p(win) * avgWin - p(loss) * avgLoss
    
    Args:
        win_rate: Probability of winning (0-1)
        avg_win: Average winning trade amount
        avg_loss: Average losing trade amount (positive value)
    
    Returns:
        Expectancy per trade
    """
    loss_rate = 1 - win_rate
    return (win_rate * avg_win) - (loss_rate * avg_loss)


# =============================================================================
# ADVANCED FORMULAS - Kelly, Bollinger, RSI
# =============================================================================

def calculate_kelly_criterion(
    win_rate: float,
    win_loss_ratio: float,
    max_kelly: float = 0.25
) -> float:
    """
    Calculate Kelly Criterion for optimal position sizing.
    
    Formula: kelly% = win_rate - ((1 - win_rate) / win_loss_ratio)
    
    Args:
        win_rate: Probability of winning (0-1)
        win_loss_ratio: Average win / Average loss
        max_kelly: Maximum kelly fraction (default 25% for safety)
    
    Returns:
        Optimal fraction of bankroll to bet (0-1)
    
    Note: We use "Half Kelly" in practice for safety
    """
    if win_loss_ratio <= 0:
        return 0.0
    
    kelly = win_rate - ((1 - win_rate) / win_loss_ratio)
    
    # Half Kelly for safety
    kelly = kelly / 2
    
    # Clamp between 0 and max
    kelly = max(0, min(kelly, max_kelly))
    
    return kelly


def calculate_bollinger_bands(
    prices: List[float],
    period: int = 20,
    std_mult: float = 2.0
) -> Tuple[float, float, float]:
    """
    Calculate Bollinger Bands.
    
    Args:
        prices: List of historical prices
        period: SMA period (default 20)
        std_mult: Standard deviation multiplier (default 2.0)
    
    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    if len(prices) < period:
        if not prices:
            return 0.0, 0.0, 0.0
        # Use what we have
        middle = np.mean(prices)
        std = np.std(prices)
        return middle + (std_mult * std), middle, middle - (std_mult * std)
    
    recent = prices[-period:]
    middle = np.mean(recent)
    std = np.std(recent)
    
    upper = middle + (std_mult * std)
    lower = middle - (std_mult * std)
    
    return upper, middle, lower


def calculate_bollinger_position(price: float, upper: float, lower: float) -> float:
    """
    Calculate price position within Bollinger Bands.
    
    Returns:
        0 = at lower band (oversold)
        0.5 = at middle
        1 = at upper band (overbought)
        <0 = below lower band (very oversold)
        >1 = above upper band (very overbought)
    """
    if upper == lower:
        return 0.5
    
    return (price - lower) / (upper - lower)


def calculate_rsi(prices: List[float], period: int = 14) -> float:
    """
    Calculate Relative Strength Index (RSI).
    
    Formula: RSI = 100 - (100 / (1 + RS))
    where RS = Average Gain / Average Loss
    
    Args:
        prices: List of historical prices
        period: RSI period (default 14)
    
    Returns:
        RSI value (0-100)
        <30 = oversold (buy signal)
        >70 = overbought (sell signal)
    """
    if len(prices) < period + 1:
        return 50.0  # Neutral
    
    # Calculate price changes
    changes = np.diff(prices[-(period + 1):])
    
    gains = [c if c > 0 else 0 for c in changes]
    losses = [-c if c < 0 else 0 for c in changes]
    
    avg_gain = np.mean(gains) if gains else 0
    avg_loss = np.mean(losses) if losses else 0
    
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def get_advanced_signal(
    price: float,
    prices: List[float],
    z_score: float,
    spread_pct: float,
    max_spread: float = 5.0
) -> Tuple[str, float, dict]:
    """
    Get trading signal using multiple indicators.
    
    Combines:
    - Z-Score
    - Bollinger Bands
    - RSI
    
    Args:
        price: Current price
        prices: Historical prices
        z_score: Pre-calculated Z-Score
        spread_pct: Current spread percentage
        max_spread: Maximum allowed spread
    
    Returns:
        Tuple of (signal, confidence, indicators)
        signal: "STRONG_BUY", "BUY", "SELL", "STRONG_SELL", "NONE"
        confidence: 0-1 confidence score
        indicators: Dict of indicator values
    """
    # Check spread first
    if spread_pct > max_spread:
        return "NONE", 0.0, {}
    
    # Calculate indicators
    upper, middle, lower = calculate_bollinger_bands(prices)
    bb_position = calculate_bollinger_position(price, upper, lower)
    rsi = calculate_rsi(prices)
    
    indicators = {
        'z_score': z_score,
        'rsi': rsi,
        'bb_position': bb_position,
        'bb_upper': upper,
        'bb_middle': middle,
        'bb_lower': lower
    }
    
    # Score each indicator (-1 to +1, negative = buy signal)
    z_signal = 0
    if z_score < -2.0:
        z_signal = -1.0  # Strong buy
    elif z_score < -1.2:
        z_signal = -0.6  # Buy
    elif z_score > 2.0:
        z_signal = 1.0   # Strong sell
    elif z_score > 1.2:
        z_signal = 0.6   # Sell
    
    rsi_signal = 0
    if rsi < 20:
        rsi_signal = -1.0  # Strong buy
    elif rsi < 30:
        rsi_signal = -0.6  # Buy
    elif rsi > 80:
        rsi_signal = 1.0   # Strong sell
    elif rsi > 70:
        rsi_signal = 0.6   # Sell
    
    bb_signal = 0
    if bb_position < 0:
        bb_signal = -1.0   # Below lower band = strong buy
    elif bb_position < 0.2:
        bb_signal = -0.6   # Near lower band = buy
    elif bb_position > 1:
        bb_signal = 1.0    # Above upper band = strong sell
    elif bb_position > 0.8:
        bb_signal = 0.6    # Near upper band = sell
    
    # Weighted average (Z-Score weighted highest)
    total_signal = (z_signal * 0.5) + (rsi_signal * 0.25) + (bb_signal * 0.25)
    
    # Determine final signal
    if total_signal <= -0.7:
        signal = "STRONG_BUY"
        confidence = min(abs(total_signal), 1.0)
    elif total_signal <= -0.4:
        signal = "BUY"
        confidence = abs(total_signal)
    elif total_signal >= 0.7:
        signal = "STRONG_SELL"
        confidence = min(total_signal, 1.0)
    elif total_signal >= 0.4:
        signal = "SELL"
        confidence = total_signal
    else:
        signal = "NONE"
        confidence = 0.0
    
    indicators['total_signal'] = total_signal
    indicators['confidence'] = confidence
    
    return signal, confidence, indicators


def calculate_dynamic_position_size(
    balance: float,
    base_pct: float,
    win_streak: int,
    lose_streak: int,
    signal_strength: float,
    kelly_fraction: float = 0.1,
    min_size: float = 0.30,
    max_size: float = 1.00
) -> float:
    """
    Calculate dynamic position size based on performance.
    
    Args:
        balance: Current balance
        base_pct: Base percentage of balance (e.g., 0.05 for 5%)
        win_streak: Current winning streak count
        lose_streak: Current losing streak count
        signal_strength: Signal confidence (0-1)
        kelly_fraction: Kelly criterion result
        min_size: Minimum position size
        max_size: Maximum position size
    
    Returns:
        Position size in USDC
    """
    # Start with base size
    size_pct = base_pct
    
    # Apply Kelly (if available and positive)
    if kelly_fraction > 0:
        size_pct = min(size_pct, kelly_fraction)
    
    # Adjust for streaks
    if win_streak >= 3:
        # Winning streak: increase size up to 50% more
        streak_mult = 1 + min(win_streak - 2, 3) * 0.15
        size_pct *= streak_mult
    elif lose_streak >= 2:
        # Losing streak: decrease size (protect capital)
        streak_mult = max(0.5, 1 - (lose_streak * 0.2))
        size_pct *= streak_mult
    
    # Adjust for signal strength
    if signal_strength >= 0.8:
        size_pct *= 1.2  # Strong signal = bigger size
    elif signal_strength < 0.5:
        size_pct *= 0.8  # Weak signal = smaller size
    
    # Calculate final size
    size = balance * size_pct
    size = max(min_size, min(max_size, size))
    
    # Don't exceed available balance
    if size > balance * 0.3:  # Max 30% in any single trade
        size = balance * 0.3
    
    return round(size, 2)


if __name__ == "__main__":
    # Test the functions
    print("🧮 Math Engine Tests\n")
    
    # Test mid price and spread
    bid, ask = 0.45, 0.55
    mid = calculate_mid_price(bid, ask)
    spread = calculate_spread_pct(bid, ask)
    print(f"Bid: {bid}, Ask: {ask}")
    print(f"Mid Price: {mid}")
    print(f"Spread: {spread:.2f}%\n")
    
    # Test Z-Score
    prices = [0.50, 0.52, 0.48, 0.51, 0.49, 0.50, 0.47, 0.53, 0.50, 0.48]
    last_price = 0.42
    z = calculate_z_score(last_price, prices)
    print(f"Prices history: {len(prices)} points")
    print(f"Last price: {last_price}")
    print(f"Z-Score: {z:.2f}")
    print(f"Signal: {'BUY (oversold)' if z < -1.2 else 'SELL' if z > 1.2 else 'NONE'}\n")
    
    # Test effective cost
    fee = 0.002
    slippage = 0.005
    spread_decimal = spread / 100
    cost = calculate_effective_cost(fee, spread_decimal, slippage)
    print(f"Effective cost: {cost:.4f} ({cost*100:.2f}%)\n")
    
    # Test position sizing
    balance = 10.0
    size = calculate_position_size(balance)
    print(f"Balance: ${balance}")
    print(f"Position size: ${size}")
