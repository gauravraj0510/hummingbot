import requests
import time
import json
import hashlib
from base64 import b64encode
from urllib.parse import urlencode
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

class LBankAPI:
    def __init__(self, api_key: str, secret_key: str, auth_method: str = "RSA"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.auth_method = auth_method
        self.base_url = "https://api.lbank.info/v2"
        
        # Format RSA key if using RSA authentication
        if auth_method == "RSA":
            self.secret_key = f"-----BEGIN RSA PRIVATE KEY-----\n{secret_key}\n-----END RSA PRIVATE KEY-----"

    def _time(self) -> int:
        return int(round(time.time() * 1e3))

    def _generate_rand_str(self) -> str:
        import random
        import string
        return "".join(random.sample(string.ascii_letters + string.digits, 35))

    def _generate_auth_signature(self, data: dict) -> str:
        # Sort data by keys
        sorted_data = dict(sorted(data.items()))
        
        # Create payload
        payload = hashlib.md5(urlencode(sorted_data).encode("utf-8")).hexdigest().upper()
        
        if self.auth_method == "RSA":
            key = RSA.importKey(self.secret_key)
            signer = PKCS1_v1_5.new(key)
            digest = SHA256.new()
            digest.update(payload.encode("utf-8"))
            return b64encode(signer.sign(digest)).decode("utf-8")
        else:
            raise ValueError("Only RSA authentication is supported")

    def get_account_balance(self) -> dict:
        """
        Get account balance information
        Returns a dictionary containing the account balances
        """
        endpoint = f"{self.base_url}/user_info.do"
        
        # Prepare authentication data
        data = {
            "api_key": self.api_key,
            "echostr": self._generate_rand_str(),
            "signature_method": self.auth_method,
            "timestamp": str(self._time())
        }
        
        # Generate signature
        signature = self._generate_auth_signature(data)
        data["sign"] = signature
        
        # Prepare headers
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # Debug output
        print("\nRequest Details:")
        print(f"Endpoint: {endpoint}")
        print("Headers:", json.dumps(headers, indent=2))
        print("Data:", json.dumps({k: v for k, v in data.items() if k != "api_key"}, indent=2))
        
        try:
            response = requests.post(endpoint, data=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting account balance: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            return None

def print_balance_info(balance_response: dict, base_token: str = "mntl", quote_token: str = "usdt"):
    """
    Print balance information for the specified trading pair
    """
    if not balance_response or "data" not in balance_response:
        print("Failed to get balance information")
        return

    data = balance_response["data"]
    
    try:
        if isinstance(data, dict):
            assets = data.get("asset", {})
            base_balance = float(assets.get(base_token, {}).get("free", 0))
            quote_balance = float(assets.get(quote_token, {}).get("free", 0))
            
            print("\nLBank Balances:")
            print("    Asset    Total")
            print("    -----    -----")
            if base_balance > 0:
                print(f"    {base_token.upper():<8} {base_balance:.4f}")
            if quote_balance > 0:
                print(f"    {quote_token.upper():<8} {quote_balance:.4f}")
            
            if base_balance == 0 and quote_balance == 0:
                print("    You have no balance on this exchange.")
        else:
            print(f"Unexpected data format: {type(data)}")
            
    except Exception as e:
        print(f"Error parsing balance information: {e}")
        print(f"Response data: {data}")

def print_response_structure(response: dict):
    """
    Print a clear view of the response structure
    """
    print("\n=== Response Structure ===")
    print(f"Status: {response.get('result', 'Unknown')}")
    
    if "data" in response:
        data = response["data"]
        if isinstance(data, dict):
            print("\nAvailable Assets:")
            assets = data.get("asset", {})
            for asset, details in assets.items():
                if float(details.get("free", 0)) > 0:  # Only show non-zero balances
                    print(f"{asset}: {details.get('free', 0)}")
    
    print("\n=== End Response Structure ===\n")

def main():
    # Your API credentials
    api_key = "7ddc9166-34fa-40e5-9392-cac770f3d426"
    secret_key = "MIICdwIBADANBgkqhkiG9w0BAQEFAASCAmEwggJdAgEAAoGBAMx48vX5CY6XKWhYeHAd6hgEDEAFd/e5B7TL2D1lqjtPzQThOvSvqZ5q2mEcA/k3/xirBOcrDkpb5XY/OmX8jGd8BpcJx4e+XxR/K22GtOvRlEJfUepJDkZr1xtEERWFZ37OYWpEt0YfxkI0Cv688bbPA/kxExQpd1dYQIA+FABBAgMBAAECgYEAg1gGKb7pRrEPJjn+U3bD0t12yQE6SOSQcLConPfbW/Is7j+H0XmtaVeWI98NJl+z+7KPmbbsnRNe2JBRAQYzYXbxj2KeJ97ZZDnbZIp/Fn9XdWAHdBKkOENBTtvvqXxNcyfsj8fPc+MMfMRnwB6zYNdxNXvC/GComtX33dMlAAECQQD7J4Es/TLc2/llpXtiZwUiXq9N/uCkwV6yYJJnfGAYfRrHx6wpUcMJWx76ivHxEWIVtz8qj0iNRvZMaA5EyhRBAkEA0Grf4tA6KrVHtwAZfKPO4W1FxLwOh8dMjSvYssCUtanfxEtlazJcMKyYWjNwD4l/ETgeUgOnlpBqAZnJjx7sAQJARKWqmBpo4Zc6lr7hd6cC7z8EGYR18HJuKMFeouyK84aWYE7CTtTrQ05lrEN4F9URgzAAEujxArSHs6CpbcHyQQJBAMgvH0RYBMaowG1BpzlUjY1wy6afisVX5GtkRgvLdgrXU5rTYGKKSIpn/R4Gcgg6ZNZBNL5JzFqN84P+Ft9lMAECQDy+6Obqs3w3VeOUa91U4NyTKkrDM3pif995lCgyvuseez4UL+BgmiXX7uRKOxbhHA9Tvc1Ht6y/oOi4kD8/ThI="
    
    # Initialize API client
    lbank = LBankAPI(api_key, secret_key, auth_method="RSA")
    
    try:
        # Get account balance
        balance = lbank.get_account_balance()
        
        if balance:
            # Print specific token balances
            print_balance_info(balance, base_token="mntl", quote_token="usdt")
        else:
            print("Failed to get account balance")
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()