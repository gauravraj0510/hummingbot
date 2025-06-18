import logging
import os
from decimal import Decimal
from typing import Dict, List, Optional

import requests
from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


# Function to get CoinGecko ID for a symbol
def get_coingecko_id(symbol: str) -> str | None:
    url = "https://api.coingecko.com/api/v3/coins/list"
    response = requests.get(url)
    response.raise_for_status() # Raise an exception for bad status codes
    data = response.json()
    
    for coin in data:
        if coin["symbol"].lower() == symbol.lower():
            return coin["id"]
    return None

# Function to get price from a specific market on CoinGecko
def get_price_from_specific_market_coingecko(base_token_id: str, quote_market_identifier: str) -> Optional[Decimal]:
    url_tickers = f"https://api.coingecko.com/api/v3/coins/{base_token_id}/tickers"
    try:
        response_tickers = requests.get(url_tickers)
        response_tickers.raise_for_status() # Raise an exception for bad status codes
        data_tickers = response_tickers.json()
    except requests.exceptions.RequestException as e:
        logging.getLogger().error(f"Error fetching ticker data from CoinGecko: {e}")
        return None

    if "tickers" in data_tickers and data_tickers["tickers"]:
        for ticker in data_tickers["tickers"]:
            market_identifier = ticker.get("market", {}).get("identifier")
            if market_identifier == quote_market_identifier:
                price_usd = ticker.get("converted_last", {}).get("usd")
                if price_usd is not None:
                    return Decimal(str(price_usd))
                else:
                    logging.getLogger().warning(f"Price data not available for {base_token_id} on market {quote_market_identifier}.")
                    return None
        # If loop finishes without finding the market
        logging.getLogger().warning(f"Market with identifier '{quote_market_identifier}' not found for {base_token_id} on CoinGecko.")
        return None
    else:
        logging.getLogger().warning(f"No ticker data found for {base_token_id} on CoinGecko.")
        return None


class SimplePMMCMCConfig(BaseClientModel):
    script_file_name: str = os.path.basename(__file__)
    exchange: str = Field("mexc")
    trading_pair: str = Field("MNTL-USDT")
    order_amount: Decimal = Field(Decimal("22000"))
    bid_spread: Decimal = Field(Decimal("0.002"))
    ask_spread: Decimal = Field(Decimal("0.002"))
    order_refresh_time: int = Field(15)
    base_token: str = Field("MNTL")  # The token to get price for
    quote_market: str = Field("osmosis", description="The CoinGecko market identifier for price source")


class SimplePMMCMC(ScriptStrategyBase):
    """
    A market making strategy that uses CoinGecko prices with OSMO as quote token.
    The bot will place two orders around the CoinGecko price in a trading_pair on
    exchange, with a distance defined by the ask_spread and bid_spread. Every order_refresh_time in seconds,
    the bot will cancel and replace the orders.
    """

    create_timestamp = 0
    _base_token_coingecko_id: str | None = None

    @classmethod
    def init_markets(cls, config: SimplePMMCMCConfig):
        cls.markets = {config.exchange: {config.trading_pair}}
        # Get CoinGecko ID during initialization
        cls._base_token_coingecko_id = get_coingecko_id(config.base_token)
        if cls._base_token_coingecko_id is None:
             logging.getLogger().error(f"Could not find CoinGecko ID for {config.base_token}. Strategy will not run.")

    def __init__(self, connectors: Dict[str, ConnectorBase], config: SimplePMMCMCConfig):
        super().__init__(connectors)
        self.config = config

    def on_tick(self):
        # Check if CoinGecko ID was found during initialization
        if self._base_token_coingecko_id is None:
             return # Do not proceed if CoinGecko ID is missing

        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            proposal: List[OrderCandidate] = self.create_proposal()
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
            self.place_orders(proposal_adjusted)
            self.create_timestamp = self.config.order_refresh_time + self.current_timestamp

    def create_proposal(self) -> List[OrderCandidate]:
        # Get price from specific CoinGecko market
        ref_price = get_price_from_specific_market_coingecko(self._base_token_coingecko_id, self.config.quote_market)
        
        if ref_price is None:
            self.logger().error(f"Could not get price for {self.config.base_token} from market {self.config.quote_market} on CoinGecko.")
            return []

        buy_price = ref_price * Decimal(1 - self.config.bid_spread)
        sell_price = ref_price * Decimal(1 + self.config.ask_spread)

        buy_order = OrderCandidate(trading_pair=self.config.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                   order_side=TradeType.BUY, amount=Decimal(self.config.order_amount), price=buy_price)

        sell_order = OrderCandidate(trading_pair=self.config.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                    order_side=TradeType.SELL, amount=Decimal(self.config.order_amount), price=sell_price)

        return [buy_order, sell_order]

    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        proposal_adjusted = self.connectors[self.config.exchange].budget_checker.adjust_candidates(proposal, all_or_none=True)
        return proposal_adjusted

    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        for order in proposal:
            self.place_order(connector_name=self.config.exchange, order=order)

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                      order_type=order.order_type, price=order.price)
        elif order.order_side == TradeType.BUY:
            self.buy(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                     order_type=order.order_type, price=order.price)

    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name=self.config.exchange):
            self.cancel(self.config.exchange, order.trading_pair, order.client_order_id)

    def did_fill_order(self, event: OrderFilledEvent):
        msg = (f"{event.trade_type.name} {round(event.amount, 2)} {event.trading_pair} {self.config.exchange} at {round(event.price, 2)}")
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg) 