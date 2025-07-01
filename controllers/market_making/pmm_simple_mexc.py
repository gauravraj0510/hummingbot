import logging
from decimal import Decimal
from typing import List, Optional
import requests
from pydantic import Field
import time

from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig

# --- CoinGecko price fetch utilities ---
def get_coingecko_id(symbol: str) -> Optional[str]:
    url = "https://api.coingecko.com/api/v3/coins/list"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        for coin in data:
            if coin["symbol"].lower() == symbol.lower():
                return coin["id"]
    except Exception as e:
        logging.getLogger().error(f"Error fetching CoinGecko ID for {symbol}: {e}")
    return None

def get_price_from_specific_market_coingecko(base_token_id: str, quote_market_identifier: str) -> Optional[Decimal]:
    url_tickers = f"https://api.coingecko.com/api/v3/coins/{base_token_id}/tickers"
    try:
        response_tickers = requests.get(url_tickers)
        response_tickers.raise_for_status()
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
        logging.getLogger().warning(f"Market with identifier '{quote_market_identifier}' not found for {base_token_id} on CoinGecko.")
        return None
    else:
        logging.getLogger().warning(f"No ticker data found for {base_token_id} on CoinGecko.")
        return None

class PMMSimpleConfig(MarketMakingControllerConfigBase):
    controller_name: str = "pmm_simple_cg"
    # As this controller is a simple version of the PMM, we are not using the candles feed
    candles_config: List[CandlesConfig] = Field(default=[])
    base_token: str = Field("MNTL", description="The token symbol to get price for from CoinGecko")
    quote_market: str = Field("osmosis", description="The CoinGecko market identifier for price source")


class PMMSimpleController(MarketMakingControllerBase):
    def __init__(self, config: PMMSimpleConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self._base_token_coingecko_id: Optional[str] = None
        self._last_cg_price: Optional[Decimal] = None
        self._last_cg_price_time: float = 0
        self._cg_price_refresh_interval: float = 30  # seconds

    def get_executor_config(self, level_id: str, price: Decimal, amount: Decimal):
        trade_type = self.get_trade_type_from_level_id(level_id)
        now = time.time()
        # Always use CoinGecko price for entry_price
        if self._base_token_coingecko_id is None:
            self._base_token_coingecko_id = get_coingecko_id(self.config.base_token)
        if self._base_token_coingecko_id is not None:
            # Only fetch new price if interval has passed
            if self._last_cg_price is None or now - self._last_cg_price_time > self._cg_price_refresh_interval:
                cg_price = get_price_from_specific_market_coingecko(self._base_token_coingecko_id, self.config.quote_market)
                if cg_price is not None:
                    self._last_cg_price = cg_price
                    self._last_cg_price_time = now
                    logging.getLogger().info(f"Fetched new CoinGecko price: {cg_price}")
                else:
                    logging.getLogger().error(f"CoinGecko price unavailable for {self.config.base_token} on {self.config.quote_market}. Order will not be created.")
                    return None
            entry_price = self._last_cg_price
        else:
            logging.getLogger().error(f"CoinGecko ID unavailable for {self.config.base_token}. Order will not be created.")
            return None
        return PositionExecutorConfig(
            timestamp=self.market_data_provider.time(),
            level_id=level_id,
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            entry_price=entry_price,
            amount=amount,
            triple_barrier_config=self.config.triple_barrier_config,
            leverage=self.config.leverage,
            side=trade_type,
        )
