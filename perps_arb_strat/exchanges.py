"""REST clients for Hyperliquid and Bybit funding rates."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional
from urllib import parse, request, error

from .config import TokenConfig

logger = logging.getLogger(__name__)


@dataclass
class FundingRate:
    """Represents a funding rate snapshot from an exchange."""

    exchange: str
    symbol: str
    rate: float
    timestamp: datetime
    raw: dict[str, object]


class HttpClient:
    """Lightweight HTTP client built on :mod:`urllib`."""

    def __init__(self, *, timeout: int = 10) -> None:
        self.timeout = timeout

    def post_json(self, url: str, payload: dict[str, object]) -> dict[str, object] | list[dict[str, object]]:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "perps-arb-strat/1.0"},
            method="POST",
        )
        return self._execute(req)

    def get_json(self, url: str, params: Optional[dict[str, object]] = None) -> dict[str, object] | list[dict[str, object]]:
        query = f"?{parse.urlencode(params)}" if params else ""
        req = request.Request(
            f"{url}{query}",
            headers={"User-Agent": "perps-arb-strat/1.0"},
            method="GET",
        )
        return self._execute(req)

    def _execute(self, req: request.Request) -> dict[str, object] | list[dict[str, object]]:
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
        except error.HTTPError as exc:  # pragma: no cover - network errors not triggered in tests
            logger.error("HTTP error %s when fetching %s", exc.code, req.full_url)
            raise
        except error.URLError as exc:  # pragma: no cover - network errors not triggered in tests
            logger.error("Failed to reach %s: %s", req.full_url, exc.reason)
            raise
        if not body:
            return {}
        return json.loads(body)


class HyperliquidClient:
    """Client for fetching Hyperliquid funding rates."""

    def __init__(self, *, base_url: str = "https://api.hyperliquid.xyz/info", http_client: Optional[HttpClient] = None) -> None:
        self.base_url = base_url
        self.http = http_client or HttpClient()

    def fetch_funding_rates(self, tokens: Iterable[TokenConfig]) -> Dict[str, FundingRate]:
        coins = sorted({token.hyperliquid_symbol for token in tokens})
        payload = {"type": "fundingRates"}
        if coins:
            payload["coins"] = coins
        response = self.http.post_json(self.base_url, payload)
        records = self._extract_records(response)
        results: Dict[str, FundingRate] = {}
        for record in records:
            coin = str(record.get("coin") or record.get("symbol") or record.get("pair") or "").upper()
            if not coin:
                continue
            raw_rate = record.get("fundingRate") or record.get("currentFunding") or record.get("funding")
            try:
                rate = float(raw_rate)
            except (TypeError, ValueError):
                continue
            timestamp = self._parse_timestamp(record.get("time") or record.get("timestamp"))
            results[coin] = FundingRate(
                exchange="Hyperliquid",
                symbol=coin,
                rate=rate,
                timestamp=timestamp,
                raw=record,
            )
        return results

    @staticmethod
    def _extract_records(response: dict[str, object] | list[dict[str, object]]) -> list[dict[str, object]]:
        if isinstance(response, list):
            return [r for r in response if isinstance(r, dict)]
        if not isinstance(response, dict):
            return []
        for key in ("fundingRates", "data", "result"):
            value = response.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
        return []

    @staticmethod
    def _parse_timestamp(value: object) -> datetime:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value) / (1_000 if value and float(value) > 1e12 else 1), tz=timezone.utc)
        return datetime.now(tz=timezone.utc)


class BybitClient:
    """Client for fetching Bybit funding rates."""

    def __init__(self, *, base_url: str = "https://api.bybit.com/v5/market/tickers", http_client: Optional[HttpClient] = None) -> None:
        self.base_url = base_url
        self.http = http_client or HttpClient()

    def fetch_funding_rates(self, tokens: Iterable[TokenConfig]) -> Dict[str, FundingRate]:
        results: Dict[str, FundingRate] = {}
        for token in tokens:
            params = {"category": "linear", "symbol": token.bybit_symbol}
            response = self.http.get_json(self.base_url, params)
            record = self._extract_record(response)
            if record is None:
                continue
            raw_rate = record.get("fundingRate")
            try:
                rate = float(raw_rate)
            except (TypeError, ValueError):
                continue
            timestamp = self._parse_timestamp(record.get("fundingTimestamp") or record.get("ts") or record.get("timestamp"))
            results[token.bybit_symbol] = FundingRate(
                exchange="Bybit",
                symbol=token.bybit_symbol,
                rate=rate,
                timestamp=timestamp,
                raw=record,
            )
        return results

    @staticmethod
    def _extract_record(response: dict[str, object] | list[dict[str, object]]) -> Optional[dict[str, object]]:
        if isinstance(response, dict):
            result = response.get("result") if isinstance(response.get("result"), dict) else None
            if result is not None:
                records = result.get("list")
                if isinstance(records, list) and records:
                    return records[0] if isinstance(records[0], dict) else None
            if isinstance(response.get("list"), list):
                records = response["list"]
                return records[0] if records and isinstance(records[0], dict) else None
        return None

    @staticmethod
    def _parse_timestamp(value: object) -> datetime:
        if isinstance(value, (int, float)):
            # Bybit returns millisecond timestamps
            return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
        if isinstance(value, str) and value.isdigit():
            return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
        return datetime.now(tz=timezone.utc)
