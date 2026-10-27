"""Time-based presence debounce. No camera or GUI dependencies."""
from dataclasses import dataclass


@dataclass
class PresenceGate:
    away_seconds: float = 3.0
    return_seconds: float = 1.0
    hidden: bool = False
    missing_since: float | None = None
    present_since: float | None = None

    def reset(self) -> None:
        self.hidden = False
        self.missing_since = None
        self.present_since = None

    def observe(self, owner_present: bool, now: float) -> str | None:
        """Return 'hide', 'restore', or None. Times must be monotonic."""
        if owner_present:
            self.missing_since = None
            if not self.hidden:
                self.present_since = None
                return None
            if self.present_since is None:
                self.present_since = now
            if now - self.present_since >= self.return_seconds:
                self.hidden = False
                self.present_since = None
                return "restore"
            return None

        self.present_since = None
        if self.hidden:
            return None
        if self.missing_since is None:
            self.missing_since = now
        if now - self.missing_since >= self.away_seconds:
            self.hidden = True
            self.missing_since = None
            return "hide"
        return None
