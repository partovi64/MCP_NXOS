from __future__ import annotations

import pytest

from nxos_mcp.guardrails.policy import Limits
from nxos_mcp.guardrails.ratelimit import DeviceGate, RateLimiter, TokenBucket
from nxos_mcp.nxapi.errors import RateLimitExceeded


@pytest.mark.asyncio
async def test_token_bucket_blocks() -> None:
    bucket = TokenBucket(rate=0.01, burst=1)
    await bucket.acquire()
    with pytest.raises(RateLimitExceeded):
        await bucket.acquire()


@pytest.mark.asyncio
async def test_device_gate() -> None:
    limiter = RateLimiter(Limits(rate_limit_per_device=100, rate_limit_burst=10))
    async with DeviceGate(limiter, "leaf-01"):
        assert True
