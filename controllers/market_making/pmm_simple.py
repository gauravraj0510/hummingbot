from decimal import Decimal
from typing import List, Optional

from pydantic import Field

from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig


class PMMSimpleConfig(MarketMakingControllerConfigBase):
    controller_name: str = "pmm_simple"
    # As this controller is a simple version of the PMM, we are not using the candles feed
    candles_config: List[CandlesConfig] = Field(default=[])
    lbank_auth_method: Optional[str] = Field(
        default="HmacSHA256",
        json_schema_extra={
            "prompt": lambda cm: (
                "Enter your LBank API Authentication Method (RSA/HmacSHA256)"
            ),
            "is_connect_key": True,
            "prompt_on_new": False,
        }
    )


class PMMSimpleController(MarketMakingControllerBase):
    def __init__(self, config: PMMSimpleConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config

    def get_connector_specific_init_params(self) -> Dict[str, Any]:
        """
        Returns a dictionary of parameters specific to the connector initialization.
        This method is designed to provide additional parameters required by the connector's __init__ method
        that are not directly part of the standard connector config map (like API keys, secret keys, etc.).
        """
        params = {
            "lbank_auth_method": self.config.lbank_auth_method
        }
        return params

    def get_executor_config(self, level_id: str, price: Decimal, amount: Decimal):
        trade_type = self.get_trade_type_from_level_id(level_id)
        return PositionExecutorConfig(
            timestamp=self.market_data_provider.time(),
            level_id=level_id,
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            entry_price=price,
            amount=amount,
            triple_barrier_config=self.config.triple_barrier_config,
            leverage=self.config.leverage,
            side=trade_type,
        )
