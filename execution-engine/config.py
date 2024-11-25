from enum import Enum
from ipaddress import IPv4Interface

import pendulum
from pydantic import Field, IPvAnyInterface
from pydantic_extra_types.pendulum_dt import DateTime, Duration
from pydantic_settings import BaseSettings, SettingsConfigDict


class RecommendationSet(str, Enum):
    """
    The supported recommendation sets.
    """

    digipod = "digipod"
    celida = "celida"


class TriggerMethod(str, Enum):
    """
    The possible methods for triggering the application of
    recommendations.
    """

    timer = "timer"
    http_request = "http_request"


class Settings(BaseSettings):
    """
    Settings for triggering the application of recommendations.
    """

    model_config = SettingsConfigDict(
        cli_parse_args=True, env_prefix="apply_recommendations_"
    )

    # Which recommendation set to apply
    recommendation_set: RecommendationSet = RecommendationSet.digipod

    # Start time
    start_time: DateTime = pendulum.parse("2024-06-01 00:00:00+01:00")
    # DateTime('2024-06-01')

    # Trigger configuration
    trigger_method: TriggerMethod = TriggerMethod.http_request
    # Time-based trigger
    trigger_run_interval: Duration = Duration(minutes=5)
    # HTTP trigger
    # The bandit security scanner does not want us to bind to all
    # interfaces by default.
    trigger_http_address: IPvAnyInterface = IPv4Interface("127.0.0.1")
    trigger_http_port: int = Field(gt=0, lt=65536, default=12345)
