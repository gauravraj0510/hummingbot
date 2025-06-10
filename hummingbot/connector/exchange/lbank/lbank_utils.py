from decimal import Decimal
from typing import Dict, Literal

from Crypto.PublicKey import RSA
from pydantic import ConfigDict, Field, model_validator
from pydantic.types import SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.connector.exchange.lbank import lbank_constants as CONSTANTS
from hummingbot.connector.exchange.lbank.lbank_auth import LbankAuth
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
)

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"


class LbankConfigMap(BaseConnectorConfigMap):
    connector: Literal["lbank"] = "lbank"
    lbank_auth_method: str = Field(
        default="HmacSHA256",
        json_schema_extra={
            "prompt": lambda cm: (
                f"Enter your LBank API Authentication Method ({'/'.join(list(CONSTANTS.LBANK_AUTH_METHODS))})"
            ),
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    lbank_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your LBank API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    lbank_secret_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your LBank secret key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="lbank")

    @model_validator(mode='after')
    def validate_auth_method(self):
        if not hasattr(self, 'lbank_auth_method'):
            return self
            
        auth_method = self.lbank_auth_method
        if auth_method not in CONSTANTS.LBANK_AUTH_METHODS:
            raise ValueError(f"Authentication Method: {auth_method} not supported. Supported methods are {', '.join(CONSTANTS.LBANK_AUTH_METHODS)}")
            
        if not hasattr(self, 'lbank_secret_key'):
            return self

        secret_key = self.lbank_secret_key.get_secret_value()
        
        if auth_method == "RSA":
            try:
                # Check if the key is already in RSA format
                if not secret_key.startswith(LbankAuth.RSA_HEADER):
                    secret_key = LbankAuth.RSA_KEY_FORMAT.format(secret_key)
                RSA.importKey(secret_key)
            except Exception as e:
                raise ValueError(f"Invalid RSA key format. Error: {str(e)}")
        elif auth_method == "HmacSHA256":
            if not secret_key or len(secret_key.strip()) == 0:
                raise ValueError("HmacSHA256 secret key cannot be empty")
            
        return self


KEYS = LbankConfigMap.model_construct()
