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
    lbank_auth_method: str = Field(
        default="RSA",
        json_schema_extra={
            "prompt": lambda cm: (
                f"Enter your LBank API Authentication Method ({'/'.join(list(CONSTANTS.LBANK_AUTH_METHODS))})"
            ),
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="lbank")

    @model_validator(mode='after')
    def validate_auth_method(self):
        if not hasattr(self, 'lbank_auth_method'):
            return self
            
        if self.lbank_auth_method not in CONSTANTS.LBANK_AUTH_METHODS:
            raise ValueError(f"Authentication Method: {self.lbank_auth_method} not supported. Supported methods are RSA/HmacSHA256")
            
        if self.lbank_auth_method == "RSA" and hasattr(self, 'lbank_secret_key'):
            try:
                RSA.importKey(LbankAuth.RSA_KEY_FORMAT.format(self.lbank_secret_key.get_secret_value()))
            except Exception as e:
                raise ValueError(f"Unable to import RSA keys. Error: {str(e)}")
        return self


KEYS = LbankConfigMap.model_construct()