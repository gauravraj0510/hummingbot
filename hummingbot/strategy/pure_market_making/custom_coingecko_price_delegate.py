from decimal import Decimal
import time
import requests

class CoinGeckoPriceDelegate:
    def __init__(self, base_token_id: str, quote_market_identifier: str, refresh_interval: float = 30):
        self.base_token_id = base_token_id
        self.quote_market_identifier = quote_market_identifier
        self.refresh_interval = refresh_interval
        self._last_price = None
        self._last_time = 0

    def get_price(self) -> Decimal:
        now = time.time()
        if self._last_price is None or now - self._last_time > self.refresh_interval:
            url = f"https://api.coingecko.com/api/v3/coins/{self.base_token_id}/tickers"
            try:
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                for ticker in data.get("tickers", []):
                    if ticker.get("market", {}).get("identifier") == self.quote_market_identifier:
                        price = ticker.get("converted_last", {}).get("usd")
                        if price is not None:
                            self._last_price = Decimal(str(price))
                            self._last_time = now
                            break
            except Exception as e:
                print(f"Error fetching CoinGecko price: {e}")
        return self._last_price 