"""Per-device token bucket + concurrency semaphores."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from nxos_mcp.guardrails.policy import Limits
from nxos_mcp.nxapi.errors import RateLimitExceeded


class TokenBucket:
    def __init__(self, rate: float, burst: int) -> None:
        self.rate = rate
        self.burst = float(burst)
        self.tokens = float(burst)
        self.updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.updated
            self.updated = now
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            if self.tokens < tokens:
                raise RateLimitExceeded(
                    "per-device rate limit exceeded",
                    hint="Slow down fan-out or raise rate_limit_per_device in guardrails.yaml",
                )
            self.tokens -= tokens


class RateLimiter:
    def __init__(self, limits: Limits) -> None:
        self._limits = limits
        self._buckets: dict[str, TokenBucket] = {}
        self._device_sems: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(limits.max_concurrent_per_device)
        )
        self._global_sem = asyncio.Semaphore(limits.global_concurrency)
        self._lock = asyncio.Lock()

    async def _bucket(self, device: str) -> TokenBucket:
        async with self._lock:
            if device not in self._buckets:
                self._buckets[device] = TokenBucket(
                    self._limits.rate_limit_per_device,
                    self._limits.rate_limit_burst,
                )
            return self._buckets[device]

    async def acquire(self, device: str) -> None:
        bucket = await self._bucket(device)
        await bucket.acquire()
        # Semaphores acquired by context manager below

    def device_slot(self, device: str) -> asyncio.Semaphore:
        return self._device_sems[device]

    @property
    def global_slot(self) -> asyncio.Semaphore:
        return self._global_sem


class DeviceGate:
    """Async context manager combining global + per-device concurrency and rate."""

    def __init__(self, limiter: RateLimiter, device: str) -> None:
        self._limiter = limiter
        self._device = device

    async def __aenter__(self) -> None:
        await self._limiter.global_slot.acquire()
        await self._limiter.device_slot(self._device).acquire()
        try:
            await self._limiter.acquire(self._device)
        except Exception:
            self._limiter.device_slot(self._device).release()
            self._limiter.global_slot.release()
            raise

    async def __aexit__(self, *args: object) -> None:
        self._limiter.device_slot(self._device).release()
        self._limiter.global_slot.release()
