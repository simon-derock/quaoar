# SerpApi key pool: most searches left wins, reserve is untouchable, quota errors rotate
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from pydantic import SecretStr

from quaoar.domain.ids import sha256_hex


class KeysExhaustedError(RuntimeError):
    pass


@dataclass(slots=True)
class KeyState:
    fingerprint: str
    secret: SecretStr
    left: int
    exhausted: bool = False


@dataclass(frozen=True, slots=True)
class KeyStatus:
    fingerprint: str
    left: int
    exhausted: bool


class KeyPool:
    def __init__(
        self,
        keys: Sequence[SecretStr],
        reserve: int,
        searches_left: Callable[[str], int],
    ) -> None:
        self._reserve = reserve
        self._states = [KeyState(fingerprint(k.get_secret_value()), k, 0) for k in keys]

        # the account endpoint is free; an unreachable account just counts as empty
        for state in self._states:
            try:
                state.left = searches_left(state.secret.get_secret_value())
            except Exception:
                state.left = 0

    def pick(self) -> KeyState:
        usable = [s for s in self._states if not s.exhausted and s.left > self._reserve]
        if not usable:
            raise KeysExhaustedError("no SerpApi key above the reserve")
        return max(usable, key=lambda s: s.left)

    def spend(self, fp: str, amount: int) -> None:
        self._find(fp).left -= amount

    def exhaust(self, fp: str) -> None:
        self._find(fp).exhausted = True

    def status(self) -> list[KeyStatus]:
        return [KeyStatus(s.fingerprint, s.left, s.exhausted) for s in self._states]

    def _find(self, fp: str) -> KeyState:
        return next(s for s in self._states if s.fingerprint == fp)


def fingerprint(key: str) -> str:
    return sha256_hex(key)[:8]
