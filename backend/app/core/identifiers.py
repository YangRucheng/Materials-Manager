from __future__ import annotations

import secrets
import threading
import time
from uuid import UUID

_RANDOM_BITS = 74
_RANDOM_MASK = (1 << _RANDOM_BITS) - 1
_lock = threading.Lock()
_last_millisecond = -1
_last_random = 0


def uuid7_string() -> str:
    """Return a canonical, monotonically increasing UUIDv7 string."""
    global _last_millisecond, _last_random

    millisecond = time.time_ns() // 1_000_000
    with _lock:
        if millisecond > _last_millisecond:
            random_bits = secrets.randbits(_RANDOM_BITS)
        else:
            millisecond = _last_millisecond
            random_bits = (_last_random + 1) & _RANDOM_MASK
            if random_bits == 0:
                millisecond += 1
        _last_millisecond = millisecond
        _last_random = random_bits

    random_a = random_bits >> 62
    random_b = random_bits & ((1 << 62) - 1)
    value = (
        ((millisecond & ((1 << 48) - 1)) << 80)
        | (0x7 << 76)
        | (random_a << 64)
        | (0b10 << 62)
        | random_b
    )
    return str(UUID(int=value))
