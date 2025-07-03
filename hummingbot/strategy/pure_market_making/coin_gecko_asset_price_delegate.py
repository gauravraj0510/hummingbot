from decimal import Decimal
from typing import Optional
import time
import logging
import requests

from hummingbot.strategy.asset_price_delegate import AssetPriceDelegate

class CoinGeckoAssetPriceDelegate(AssetPriceDelegate):
    def __init__(self, base_token: str, quote_market_identifier: str, refresh_interval: float = 30.0):
        super().__init__()
        self._base_token = base_token
        self._quote_market_identifier = quote_market_identifier
        self._refresh_interval = refresh_interval
        self._base_token_coingecko_id: Optional[str] = None
        self._last_cg_price: Optional[Decimal] = None
        self._last_cg_price_time: float = 0
        self._logger = logging.getLogger(__name__)
        self._logger.info(f"[CoinGeckoAssetPriceDelegate] Initialized with base_token={base_token}, quote_market_identifier={quote_market_identifier}, refresh_interval={refresh_interval}")

    @property
    def ready(self) -> bool:
        ready = self._last_cg_price is not None
        self._logger.info(f"[CoinGeckoAssetPriceDelegate] .ready called, value: {ready}, last_cg_price: {self._last_cg_price}")
        return ready

    @property
    def market(self):
        # Not tied to a market, return None
        return None

    def get_price_by_type(self, price_type) -> Decimal:
        price = self.c_get_mid_price()
        self._logger.info(f"[CoinGeckoAssetPriceDelegate] get_price_by_type({price_type}) -> {price}")
        return price

    def c_get_mid_price(self):
        now = time.time()
        self._logger.info(f"[CoinGeckoAssetPriceDelegate] c_get_mid_price called at {now}")
        if self._base_token_coingecko_id is None:
            self._logger.info(f"[CoinGeckoAssetPriceDelegate] Fetching CoinGecko ID for {self._base_token}")
            self._base_token_coingecko_id = self.get_coingecko_id(self._base_token)
            self._logger.info(f"[CoinGeckoAssetPriceDelegate] CoinGecko ID result: {self._base_token_coingecko_id}")
        if self._base_token_coingecko_id is not None:
            if self._last_cg_price is None or now - self._last_cg_price_time > self._refresh_interval:
                self._logger.info(f"[CoinGeckoAssetPriceDelegate] Fetching price for {self._base_token_coingecko_id} on {self._quote_market_identifier}")
                cg_price = self.get_price_from_specific_market_coingecko(self._base_token_coingecko_id, self._quote_market_identifier)
                self._logger.info(f"[CoinGeckoAssetPriceDelegate] Price fetch result: {cg_price}")
                if cg_price is not None:
                    self._last_cg_price = cg_price
                    self._last_cg_price_time = now
                    self._logger.info(f"[CoinGeckoAssetPriceDelegate] Updated last_cg_price: {cg_price}")
                else:
                    self._logger.error(f"CoinGecko price unavailable for {self._base_token} on {self._quote_market_identifier}.")
        else:
            self._logger.error(f"CoinGecko ID unavailable for {self._base_token}.")
        self._logger.info(f"[CoinGeckoAssetPriceDelegate] Returning price: {self._last_cg_price}")
        return self._last_cg_price if self._last_cg_price is not None else Decimal('NaN')

    @staticmethod
    def get_coingecko_id(symbol: str) -> Optional[str]:
        url = "https://api.coingecko.com/api/v3/coins/list"
        try:
            logging.getLogger(__name__).info(f"[CoinGeckoAssetPriceDelegate] Requesting CoinGecko ID for symbol: {symbol}")
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            for coin in data:
                if coin["symbol"].lower() == symbol.lower():
                    logging.getLogger(__name__).info(f"[CoinGeckoAssetPriceDelegate] Found CoinGecko ID: {coin['id']} for symbol: {symbol}")
                    return coin["id"]
        except Exception as e:
            logging.getLogger(__name__).error(f"Error fetching CoinGecko ID for {symbol}: {e}")
        return None

    @staticmethod
    def get_price_from_specific_market_coingecko(base_token_id: str, quote_market_identifier: str) -> Optional[Decimal]:
        url_tickers = f"https://api.coingecko.com/api/v3/coins/{base_token_id}/tickers"
        try:
            logging.getLogger(__name__).info(f"[CoinGeckoAssetPriceDelegate] Requesting price for {base_token_id} on {quote_market_identifier}")
            response_tickers = requests.get(url_tickers)
            response_tickers.raise_for_status()
            data_tickers = response_tickers.json()
        except requests.exceptions.RequestException as e:
            logging.getLogger(__name__).error(f"Error fetching ticker data from CoinGecko: {e}")
            return None

        if "tickers" in data_tickers and data_tickers["tickers"]:
            for ticker in data_tickers["tickers"]:
                market_identifier = ticker.get("market", {}).get("identifier")
                if market_identifier == quote_market_identifier:
                    price_usd = ticker.get("converted_last", {}).get("usd")
                    if price_usd is not None:
                        logging.getLogger(__name__).info(f"[CoinGeckoAssetPriceDelegate] Found price: {price_usd} for {base_token_id} on {quote_market_identifier}")
                        return Decimal(str(price_usd))
                    else:
                        logging.getLogger(__name__).warning(f"Price data not available for {base_token_id} on market {quote_market_identifier}.")
                        return None
            logging.getLogger(__name__).warning(f"Market with identifier '{quote_market_identifier}' not found for {base_token_id} on CoinGecko.")
            return None
        else:
            logging.getLogger(__name__).warning(f"No ticker data found for {base_token_id} on CoinGecko.")
            return None 