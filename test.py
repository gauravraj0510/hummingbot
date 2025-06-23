from decimal import Decimal
from typing import Optional
import requests


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
        print("Data:", data_tickers)
    except requests.exceptions.RequestException as e:
        # logging.getLogger().error(f"Error fetching ticker data from CoinGecko: {e}")
        return None

    if "tickers" in data_tickers and data_tickers["tickers"]:
        for ticker in data_tickers["tickers"]:
            market_identifier = ticker.get("market", {}).get("identifier")
            if market_identifier == quote_market_identifier:
                price_usd = ticker.get("converted_last", {}).get("usd")
                if price_usd is not None:
                    return Decimal(str(price_usd))
                else:
                    # logging.getLogger().warning(f"Price data not available for {base_token_id} on market {quote_market_identifier}.")
                    return None
        # If loop finishes without finding the market
        # logging.getLogger().warning(f"Market with identifier '{quote_market_identifier}' not found for {base_token_id} on CoinGecko.")
        return None
    else:
        # logging.getLogger().warning(f"No ticker data found for {base_token_id} on CoinGecko.")
        return None
base_id = get_coingecko_id("MNTL")
print(get_price_from_specific_market_coingecko(base_id, "osmosis"))