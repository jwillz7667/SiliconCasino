"""
Oracle service for resolving prediction markets.

Fetches external data to determine market outcomes.
Supports multiple data sources with fallback.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

import httpx


class OracleSource(Enum):
    """Supported oracle data sources."""

    COINGECKO = "coingecko"
    MANUAL = "manual"
    CUSTOM = "custom"


@dataclass
class OracleResult:
    """Result from an oracle query."""

    source: OracleSource
    value: Any
    timestamp: datetime
    raw_data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "raw_data": self.raw_data,
        }


class OracleService:
    """
    Service for fetching external data to resolve prediction markets.
    """

    COINGECKO_API = "https://api.coingecko.com/api/v3"

    def __init__(self, timeout: float = 10.0):
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def get_crypto_price(self, coin_id: str, vs_currency: str = "usd") -> OracleResult:
        """
        Get current cryptocurrency price from CoinGecko.

        Args:
            coin_id: CoinGecko coin ID (e.g., "bitcoin", "ethereum")
            vs_currency: Target currency (default: "usd")
        """
        try:
            response = await self._client.get(
                f"{self.COINGECKO_API}/simple/price",
                params={
                    "ids": coin_id,
                    "vs_currencies": vs_currency,
                    "include_24hr_change": "true",
                    "include_market_cap": "true",
                },
            )
            response.raise_for_status()
            data = response.json()

            if coin_id not in data:
                raise ValueError(f"Unknown coin: {coin_id}")

            price = data[coin_id].get(vs_currency)

            return OracleResult(
                source=OracleSource.COINGECKO,
                value=Decimal(str(price)) if price else None,
                timestamp=datetime.now(timezone.utc),
                raw_data=data[coin_id],
            )
        except Exception as e:
            return OracleResult(
                source=OracleSource.COINGECKO,
                value=None,
                timestamp=datetime.now(timezone.utc),
                raw_data={"error": str(e)},
            )

    async def get_crypto_market_cap(self, coin_id: str) -> OracleResult:
        """Get market cap for a cryptocurrency."""
        try:
            response = await self._client.get(
                f"{self.COINGECKO_API}/coins/{coin_id}",
                params={"localization": "false", "tickers": "false"},
            )
            response.raise_for_status()
            data = response.json()

            market_cap = data.get("market_data", {}).get("market_cap", {}).get("usd")

            return OracleResult(
                source=OracleSource.COINGECKO,
                value=market_cap,
                timestamp=datetime.now(timezone.utc),
                raw_data={
                    "market_cap_usd": market_cap,
                    "name": data.get("name"),
                    "symbol": data.get("symbol"),
                },
            )
        except Exception as e:
            return OracleResult(
                source=OracleSource.COINGECKO,
                value=None,
                timestamp=datetime.now(timezone.utc),
                raw_data={"error": str(e)},
            )

    async def resolve_market(
        self,
        oracle_source: str,
        oracle_data: dict[str, Any],
    ) -> tuple[bool | None, OracleResult]:
        """
        Attempt to resolve a market based on its oracle configuration.

        Returns:
            Tuple of (outcome, oracle_result)
            outcome is True for YES, False for NO, None if unable to resolve
        """
        if oracle_source == "coingecko":
            return await self._resolve_coingecko(oracle_data)
        elif oracle_source == "manual":
            # Manual markets must be resolved by admin
            return None, OracleResult(
                source=OracleSource.MANUAL,
                value=None,
                timestamp=datetime.now(timezone.utc),
                raw_data={"message": "Manual resolution required"},
            )
        else:
            return None, OracleResult(
                source=OracleSource.CUSTOM,
                value=None,
                timestamp=datetime.now(timezone.utc),
                raw_data={"error": f"Unknown oracle source: {oracle_source}"},
            )

    async def _resolve_coingecko(
        self,
        oracle_data: dict[str, Any],
    ) -> tuple[bool | None, OracleResult]:
        """Resolve a CoinGecko-based market."""
        asset = oracle_data.get("asset")
        threshold = oracle_data.get("threshold")
        comparison = oracle_data.get("comparison")

        if comparison == "eth_vs_btc":
            # Special case: ETH market cap vs BTC market cap
            eth_result = await self.get_crypto_market_cap("ethereum")
            btc_result = await self.get_crypto_market_cap("bitcoin")

            if eth_result.value is None or btc_result.value is None:
                return None, OracleResult(
                    source=OracleSource.COINGECKO,
                    value=None,
                    timestamp=datetime.now(timezone.utc),
                    raw_data={
                        "eth": eth_result.raw_data,
                        "btc": btc_result.raw_data,
                    },
                )

            outcome = eth_result.value > btc_result.value
            return outcome, OracleResult(
                source=OracleSource.COINGECKO,
                value={"eth_mcap": eth_result.value, "btc_mcap": btc_result.value},
                timestamp=datetime.now(timezone.utc),
                raw_data={
                    "eth": eth_result.raw_data,
                    "btc": btc_result.raw_data,
                    "outcome": outcome,
                },
            )

        elif asset and threshold:
            # Price threshold comparison
            result = await self.get_crypto_price(asset)

            if result.value is None:
                return None, result

            outcome = result.value >= Decimal(str(threshold))
            return outcome, OracleResult(
                source=OracleSource.COINGECKO,
                value=float(result.value),
                timestamp=datetime.now(timezone.utc),
                raw_data={
                    **result.raw_data,
                    "threshold": threshold,
                    "outcome": outcome,
                },
            )

        return None, OracleResult(
            source=OracleSource.COINGECKO,
            value=None,
            timestamp=datetime.now(timezone.utc),
            raw_data={"error": "Invalid oracle_data configuration"},
        )


# Global oracle service
oracle_service = OracleService()
