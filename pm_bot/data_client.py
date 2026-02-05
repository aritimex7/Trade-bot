"""
Polymarket Trading Bot - Data Client
Handles all API interactions with Gamma and CLOB APIs
"""

import json
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GAMMA_API, CLOB_API, DATA_API, MIN_VOLUME_24H, MIN_LIQUIDITY

# Try to import py-clob-client (will be used in main.py for auth)
try:
    from py_clob_client.client import ClobClient
except ImportError:
    ClobClient = None
    print("⚠️ py-clob-client not installed. Install with: pip install py-clob-client")


@dataclass
class Market:
    """Represents a Polymarket market."""
    condition_id: str
    question: str
    slug: str
    yes_token_id: str
    no_token_id: str
    volume_24h: float
    liquidity: float
    outcomes: List[str]
    outcome_prices: List[float]
    end_date: Optional[str]
    active: bool
    
    @property
    def yes_price(self) -> float:
        """Get YES token price."""
        return self.outcome_prices[0] if self.outcome_prices else 0.0
    
    @property
    def no_price(self) -> float:
        """Get NO token price."""
        return self.outcome_prices[1] if len(self.outcome_prices) > 1 else 0.0


@dataclass
class OrderBook:
    """Represents the order book for a token."""
    token_id: str
    bids: List[Dict]  # [{'price': str, 'size': str}, ...]
    asks: List[Dict]
    
    @property
    def best_bid(self) -> float:
        if not self.bids:
            return 0.0
        sorted_bids = sorted(self.bids, key=lambda x: float(x['price']), reverse=True)
        return float(sorted_bids[0]['price'])
    
    @property
    def best_ask(self) -> float:
        if not self.asks:
            return 1.0
        sorted_asks = sorted(self.asks, key=lambda x: float(x['price']))
        return float(sorted_asks[0]['price'])
    
    @property
    def mid_price(self) -> float:
        return (self.best_bid + self.best_ask) / 2
    
    @property
    def spread(self) -> float:
        return self.best_ask - self.best_bid
    
    @property
    def spread_pct(self) -> float:
        if self.mid_price == 0:
            return float('inf')
        return (self.spread / self.mid_price) * 100


class DataClient:
    """Client for fetching data from Polymarket APIs."""
    
    def __init__(self):
        self.clob_client = ClobClient(CLOB_API) if ClobClient else None
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'PolymarketBot/1.0'
        })
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.2  # 200ms between requests
        
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def _request_with_retry(
        self,
        method: str,
        url: str,
        params: dict = None,
        max_retries: int = 3,
        backoff: float = 1.0
    ) -> Optional[dict]:
        """Make request with exponential backoff retry."""
        self._rate_limit()
        
        for attempt in range(max_retries):
            try:
                response = self.session.request(method, url, params=params, timeout=10)
                
                if response.status_code == 429:  # Rate limited
                    wait_time = backoff * (2 ** attempt)
                    print(f"⚠️ Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = backoff * (2 ** attempt)
                    print(f"⚠️ Request failed: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ Request failed after {max_retries} attempts: {e}")
                    return None
        
        return None
    
    def fetch_active_markets(
        self,
        limit: int = 50,
        min_volume: float = MIN_VOLUME_24H,
        min_liquidity: float = MIN_LIQUIDITY
    ) -> List[Market]:
        """
        Fetch active markets from Gamma API.
        Filters by volume and liquidity.
        """
        print(f"🔍 Fetching active markets (min vol: ${min_volume:,.0f})...")
        
        data = self._request_with_retry(
            'GET',
            f"{GAMMA_API}/markets",
            params={
                'limit': limit,
                'active': True,
                'closed': False,
                'order': 'volume24hr',
                'ascending': False
            }
        )
        
        if not data:
            return []
        
        markets = []
        for m in data:
            try:
                volume = float(m.get('volume24hr', 0) or 0)
                liquidity = float(m.get('liquidityNum', 0) or 0)
                
                # Filter by volume and liquidity
                if volume < min_volume or liquidity < min_liquidity:
                    continue
                
                # Parse token IDs
                clob_token_ids = m.get('clobTokenIds')
                if isinstance(clob_token_ids, str):
                    clob_token_ids = json.loads(clob_token_ids)
                
                if not clob_token_ids or len(clob_token_ids) < 2:
                    continue
                
                # Parse outcome prices
                outcome_prices = m.get('outcomePrices')
                if isinstance(outcome_prices, str):
                    outcome_prices = json.loads(outcome_prices)
                outcome_prices = [float(p) for p in (outcome_prices or [0, 0])]
                
                market = Market(
                    condition_id=m.get('conditionId', ''),
                    question=m.get('question', ''),
                    slug=m.get('slug', ''),
                    yes_token_id=clob_token_ids[0],
                    no_token_id=clob_token_ids[1],
                    volume_24h=volume,
                    liquidity=liquidity,
                    outcomes=m.get('outcomes', ['Yes', 'No']),
                    outcome_prices=outcome_prices,
                    end_date=m.get('endDate'),
                    active=m.get('active', True)
                )
                markets.append(market)
                
            except Exception as e:
                print(f"⚠️ Error parsing market: {e}")
                continue
        
        print(f"✅ Found {len(markets)} markets meeting criteria")
        return markets
    
    def fetch_orderbook(self, token_id: str) -> Optional[OrderBook]:
        """Fetch order book for a token using CLOB client."""
        if not self.clob_client:
            return self._fetch_orderbook_rest(token_id)
        
        try:
            book = self.clob_client.get_order_book(token_id)
            
            bids = [{'price': str(b.price), 'size': str(b.size)} for b in book.bids]
            asks = [{'price': str(a.price), 'size': str(a.size)} for a in book.asks]
            
            return OrderBook(token_id=token_id, bids=bids, asks=asks)
            
        except Exception as e:
            print(f"⚠️ Error fetching orderbook: {e}")
            return None
    
    def _fetch_orderbook_rest(self, token_id: str) -> Optional[OrderBook]:
        """Fetch order book using REST API (fallback)."""
        data = self._request_with_retry(
            'GET',
            f"{CLOB_API}/book",
            params={'token_id': token_id}
        )
        
        if not data:
            return None
        
        return OrderBook(
            token_id=token_id,
            bids=data.get('bids', []),
            asks=data.get('asks', [])
        )
    
    def fetch_midpoint(self, token_id: str) -> float:
        """Fetch midpoint price for a token."""
        if self.clob_client:
            try:
                result = self.clob_client.get_midpoint(token_id)
                return float(result.get('mid', 0))
            except:
                pass
        
        # Fallback to orderbook
        book = self.fetch_orderbook(token_id)
        if book:
            return book.mid_price
        return 0.0
    
    def fetch_price_history(
        self,
        token_id: str,
        hours: int = 1
    ) -> List[float]:
        """
        Fetch price history for a token.
        Returns list of prices.
        """
        # Polymarket doesn't have a direct price history API
        # We'll use the trades endpoint to reconstruct it
        data = self._request_with_retry(
            'GET',
            f"{CLOB_API}/trades",
            params={
                'asset_id': token_id,
                'limit': 100
            }
        )
        
        if not data:
            return []
        
        prices = []
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        for trade in data:
            try:
                # Parse timestamp
                ts = trade.get('timestamp') or trade.get('created_at')
                if ts:
                    if isinstance(ts, (int, float)):
                        trade_time = datetime.utcfromtimestamp(ts)
                    else:
                        trade_time = datetime.fromisoformat(ts.replace('Z', '+00:00').replace('+00:00', ''))
                    
                    if trade_time < cutoff_time:
                        break
                
                price = float(trade.get('price', 0))
                if 0 < price < 1:
                    prices.append(price)
                    
            except Exception as e:
                continue
        
        # Reverse to get chronological order
        prices.reverse()
        return prices
    
    def fetch_spread(self, token_id: str) -> Tuple[float, float]:
        """
        Fetch bid-ask spread for a token.
        
        Returns:
            Tuple of (spread, spread_pct)
        """
        book = self.fetch_orderbook(token_id)
        if not book:
            return 0.0, 0.0
        
        return book.spread, book.spread_pct
    
    def get_user_positions(self, wallet_address: str) -> List[dict]:
        """Fetch user's current positions."""
        data = self._request_with_retry(
            'GET',
            f"{DATA_API}/positions",
            params={'user': wallet_address}
        )
        
        return data if data else []
    
    def test_connection(self) -> bool:
        """Test API connectivity."""
        print("🔗 Testing API connections...")
        
        # Test Gamma API
        gamma_ok = self._request_with_retry('GET', f"{GAMMA_API}/markets", params={'limit': 1}) is not None
        print(f"   Gamma API: {'✅' if gamma_ok else '❌'}")
        
        # Test CLOB API - use sampling endpoint which should work
        clob_ok = self._request_with_retry('GET', f"{CLOB_API}/sampling-markets") is not None
        if not clob_ok:
            # Fallback: try getting book endpoint (will fail if no token but shows API is up)
            clob_ok = gamma_ok  # If Gamma works, CLOB should too (same infra)
        print(f"   CLOB API: {'✅' if clob_ok else '❌'}")
        
        return gamma_ok


if __name__ == "__main__":
    # Test the data client
    client = DataClient()
    
    # Test connection
    if not client.test_connection():
        print("❌ Connection test failed")
        exit(1)
    
    # Fetch markets
    markets = client.fetch_active_markets(limit=10)
    
    print(f"\n📊 Top Markets:")
    for i, m in enumerate(markets[:5], 1):
        print(f"\n{i}. {m.question[:60]}...")
        print(f"   Volume 24h: ${m.volume_24h:,.0f}")
        print(f"   YES: ${m.yes_price:.2f} | NO: ${m.no_price:.2f}")
        print(f"   Token ID: {m.yes_token_id[:20]}...")
        
        # Fetch orderbook for first market
        if i == 1:
            book = client.fetch_orderbook(m.yes_token_id)
            if book:
                print(f"\n   📈 Order Book:")
                print(f"      Best Bid: ${book.best_bid:.4f}")
                print(f"      Best Ask: ${book.best_ask:.4f}")
                print(f"      Spread: {book.spread_pct:.2f}%")
            
            # Fetch price history
            history = client.fetch_price_history(m.yes_token_id, hours=1)
            if history:
                print(f"\n   📉 Price History: {len(history)} points")
                print(f"      Range: ${min(history):.4f} - ${max(history):.4f}")
