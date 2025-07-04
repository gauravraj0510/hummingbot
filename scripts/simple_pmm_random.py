import logging
import os
import random
from decimal import Decimal
from typing import Dict, List

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class SimplePMMRandomConfig(BaseClientModel):
    script_file_name: str = os.path.basename(__file__)
    exchange: str = Field("mexc")
    trading_pair: str = Field("MNTL-USDT")
    min_order_amount: Decimal = Field(22000)  # Minimum order amount
    max_order_amount: Decimal = Field(44000)  # Maximum order amount
    bid_spread: Decimal = Field(0.001)
    ask_spread: Decimal = Field(0.001)
    min_order_refresh_time: int = Field(5)  # Minimum refresh time in seconds
    max_order_refresh_time: int = Field(15)  # Maximum refresh time in seconds
    price_type: str = Field("mid")


class SimplePMMRandom(ScriptStrategyBase):
    """
    A market making strategy that uses random ranges for order refresh time and order amount.
    The bot will place two orders around the price_source (mid price or last traded price) in a trading_pair on
    exchange, with a distance defined by the ask_spread and bid_spread. The order refresh time and order amount
    will be randomly selected from their respective ranges each time orders are placed.
    Orders are placed atomically - either both buy and sell orders are placed, or neither is placed.
    """

    create_timestamp = 0
    price_source = PriceType.MidPrice

    @classmethod
    def init_markets(cls, config: SimplePMMRandomConfig):
        cls.markets = {config.exchange: {config.trading_pair}}
        cls.price_source = PriceType.LastTrade if config.price_type == "last" else PriceType.MidPrice

    def __init__(self, connectors: Dict[str, ConnectorBase], config: SimplePMMRandomConfig):
        super().__init__(connectors)
        self.config = config

    def on_tick(self):
        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            proposal: List[OrderCandidate] = self.create_proposal()
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
            
            # Check if we can place both orders
            if self.can_place_both_orders(proposal_adjusted):
                self.place_orders(proposal_adjusted)
            else:
                msg = "Cannot place both orders - insufficient balance for one or both sides"
                self.log_with_clock(logging.WARNING, msg)
                self.notify_hb_app_with_timestamp(msg) 
            
            # Generate random refresh time between min and max
            random_refresh_time = random.randint(
                self.config.min_order_refresh_time,
                self.config.max_order_refresh_time
            )
            self.create_timestamp = random_refresh_time + self.current_timestamp

    def can_place_both_orders(self, proposal: List[OrderCandidate]) -> bool:
        """
        Check if we have sufficient balance to place both buy and sell orders.
        Returns True only if both orders can be placed.
        """
        if len(proposal) != 2:
            return False
            
        connector = self.connectors[self.config.exchange]
        base, quote = self.config.trading_pair.split("-")
        
        # Check buy order (quote currency needed)
        buy_order = next((order for order in proposal if order.order_side == TradeType.BUY), None)
        if buy_order:
            quote_balance = connector.get_available_balance(quote)
            required_quote = buy_order.amount * buy_order.price
            if quote_balance < required_quote:
                return False
        
        # Check sell order (base currency needed)
        sell_order = next((order for order in proposal if order.order_side == TradeType.SELL), None)
        if sell_order:
            base_balance = connector.get_available_balance(base)
            if base_balance < sell_order.amount:
                return False
        
        return True

    def create_proposal(self) -> List[OrderCandidate]:
        ref_price = self.connectors[self.config.exchange].get_price_by_type(self.config.trading_pair, self.price_source)
        buy_price = ref_price * Decimal(1 - self.config.bid_spread)
        sell_price = ref_price * Decimal(1 + self.config.ask_spread)

        # Generate random order amount between min and max
        random_amount = Decimal(str(random.uniform(
            float(self.config.min_order_amount),
            float(self.config.max_order_amount)
        )))

        buy_order = OrderCandidate(trading_pair=self.config.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                   order_side=TradeType.BUY, amount=random_amount, price=buy_price)

        sell_order = OrderCandidate(trading_pair=self.config.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                    order_side=TradeType.SELL, amount=random_amount, price=sell_price)

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