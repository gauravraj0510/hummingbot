from lbank.old_api import BlockHttpClient
import logging
import json
import time
from typing import Dict, Any, Optional, List

class LBankClient:
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://api.lbkex.com/"):
        """
        Initialize LBank client with API credentials
        
        Args:
            api_key (str): Your LBank API key
            api_secret (str): Your LBank API secret
            base_url (str): LBank API base URL
        """
        self.client = BlockHttpClient(
            sign_method="RSA",  # Using RSA signing method
            api_key=api_key,
            api_secret=api_secret,
            base_url=base_url,
            log_level=logging.INFO
        )
    
    def get_detailed_account_info(self) -> List[Dict[str, Any]]:
        """Get detailed account information including network details"""
        return self.client.http_request("post", "v2/supplement/user_info.do")
    
    def get_token_details(self, token: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific token including network details
        
        Args:
            token (str): Token symbol (e.g., 'mntl', 'usdt')
        """
        account_info = self.get_detailed_account_info()
        for asset in account_info:
            if asset['coin'].lower() == token.lower():
                return asset
        return {}
    
    def get_token_balance(self, token: str) -> Dict[str, Any]:
        """
        Get balance for a specific token
        
        Args:
            token (str): Token symbol (e.g., 'mntl', 'usdt')
        """
        token_details = self.get_token_details(token)
        if token_details:
            return {
                'token': token,
                'usable': token_details.get('usableAmt', '0'),
                'total': token_details.get('assetAmt', '0'),
                'frozen': token_details.get('freezeAmt', '0'),
                'networks': token_details.get('networkList', [])
            }
        return {
            'token': token,
            'usable': '0',
            'total': '0',
            'frozen': '0',
            'networks': []
        }

class BalanceManager:
    def __init__(self, api_key: str, api_secret: str, target_balance: float = 60000, min_difference: float = 11500):
        """
        Initialize balance manager
        
        Args:
            api_key (str): LBank API key
            api_secret (str): LBank API secret
            target_balance (float): Target balance to maintain
            min_difference (float): Minimum difference required to trigger rebalancing
        """
        self.client = LBankClient(api_key, api_secret)
        self.target_balance = target_balance
        self.min_difference = min_difference
        self.base_token = "mntl"
        self.quote_token = "usdt"
        self.trading_pair = f"{self.base_token}_{self.quote_token}"
    
    def get_current_price(self) -> float:
        """Get current price of MNTL/USDT"""
        response = self.client.client.http_request("get", "v2/supplement/ticker/price.do")
        for pair in response:
            if pair['symbol'] == self.trading_pair:
                return float(pair['price'])
        raise Exception(f"Could not find price for {self.trading_pair}")
    
    def get_current_balance(self) -> float:
        """Get current MNTL balance"""
        balance_info = self.client.get_token_balance(self.base_token)
        return float(balance_info['usable'])
    
    def execute_market_order(self, order_type: str, amount: float) -> Dict[str, Any]:
        """
        Execute a market order
        
        Args:
            order_type (str): 'buy_market' or 'sell_market'
            amount (float): Amount to trade
        """
        payload = {
            "symbol": self.trading_pair,
            "type": order_type,
            "amount": str(amount)
        }
        return self.client.client.http_request("post", "v2/supplement/create_order.do", payload=payload)
    
    def adjust_balance(self) -> None:
        """Adjust balance to target by executing market orders"""
        try:
            current_balance = self.get_current_balance()
            current_price = self.get_current_price()
            
            print(f"\nCurrent Status:")
            print(f"Current Balance: {current_balance} MNTL")
            print(f"Target Balance: {self.target_balance} MNTL")
            print(f"Current Price: {current_price} USDT")
            
            if current_balance < self.target_balance:
                # Need to buy more MNTL
                difference = self.target_balance - current_balance
                if difference >= self.min_difference:
                    usdt_amount = difference * current_price
                    print(f"\nBuying {difference} MNTL (≈{usdt_amount} USDT)")
                    order = self.execute_market_order("buy_market", usdt_amount)
                    print(f"Order executed: {json.dumps(order, indent=2)}")
                else:
                    print(f"\nDifference ({difference} MNTL) is less than minimum threshold ({self.min_difference} MNTL). No action taken.")
                
            elif current_balance > self.target_balance:
                # Need to sell excess MNTL
                difference = current_balance - self.target_balance
                if difference >= self.min_difference:
                    print(f"\nSelling {difference} MNTL")
                    order = self.execute_market_order("sell_market", difference)
                    print(f"Order executed: {json.dumps(order, indent=2)}")
                else:
                    print(f"\nDifference ({difference} MNTL) is less than minimum threshold ({self.min_difference} MNTL). No action taken.")
                
            else:
                print("\nBalance is already at target level")
                
        except Exception as e:
            print(f"Error adjusting balance: {str(e)}")

def main():
    # LBank Ext 2 RSA Keys
    api_key = "7ddc9166-34fa-40e5-9392-cac770f3d426"
    api_secret = "MIICdwIBADANBgkqhkiG9w0BAQEFAASCAmEwggJdAgEAAoGBAMx48vX5CY6XKWhYeHAd6hgEDEAFd/e5B7TL2D1lqjtPzQThOvSvqZ5q2mEcA/k3/xirBOcrDkpb5XY/OmX8jGd8BpcJx4e+XxR/K22GtOvRlEJfUepJDkZr1xtEERWFZ37OYWpEt0YfxkI0Cv688bbPA/kxExQpd1dYQIA+FABBAgMBAAECgYEAg1gGKb7pRrEPJjn+U3bD0t12yQE6SOSQcLConPfbW/Is7j+H0XmtaVeWI98NJl+z+7KPmbbsnRNe2JBRAQYzYXbxj2KeJ97ZZDnbZIp/Fn9XdWAHdBKkOENBTtvvqXxNcyfsj8fPc+MMfMRnwB6zYNdxNXvC/GComtX33dMlAAECQQD7J4Es/TLc2/llpXtiZwUiXq9N/uCkwV6yYJJnfGAYfRrHx6wpUcMJWx76ivHxEWIVtz8qj0iNRvZMaA5EyhRBAkEA0Grf4tA6KrVHtwAZfKPO4W1FxLwOh8dMjSvYssCUtanfxEtlazJcMKyYWjNwD4l/ETgeUgOnlpBqAZnJjx7sAQJARKWqmBpo4Zc6lr7hd6cC7z8EGYR18HJuKMFeouyK84aWYE7CTtTrQ05lrEN4F9URgzAAEujxArSHs6CpbcHyQQJBAMgvH0RYBMaowG1BpzlUjY1wy6afisVX5GtkRgvLdgrXU5rTYGKKSIpn/R4Gcgg6ZNZBNL5JzFqN84P+Ft9lMAECQDy+6Obqs3w3VeOUa91U4NyTKkrDM3pif995lCgyvuseez4UL+BgmiXX7uRKOxbhHA9Tvc1Ht6y/oOi4kD8/ThI="
    
    # Initialize balance manager with minimum difference threshold
    manager = BalanceManager(api_key, api_secret, min_difference=11500)
    
    try:
        # Adjust balance to target
        manager.adjust_balance()
        
    except Exception as e:
        print(f"Error in main: {str(e)}")

if __name__ == "__main__":
    main() 