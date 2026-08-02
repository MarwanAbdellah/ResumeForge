"""Small dependency-free metrics registry for local and platform scraping."""

from collections import Counter, defaultdict
from threading import Lock


class Metrics:
    def __init__(self):
        self.counters = Counter()
        self.timings: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def increment(self, name: str, value: int = 1, **labels) -> None:
        key = self._key(name, labels)
        with self._lock:
            self.counters[key] += value

    def observe(self, name: str, value_ms: float, **labels) -> None:
        key = self._key(name, labels)
        with self._lock:
            self.timings[key].append(value_ms)

    def prometheus(self) -> str:
        lines = []
        with self._lock:
            for key, value in self.counters.items():
                lines.append(f"{key} {value}")
            for key, values in self.timings.items():
                if values:
                    lines.append(f"{key}_count {len(values)}")
                    lines.append(f"{key}_sum {sum(values) / 1000:.6f}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _key(name: str, labels: dict) -> str:
        if not labels:
            return name
        suffix = ",".join(f'{key}="{str(value).replace(chr(34), "")}"' for key, value in sorted(labels.items()))
        return f"{name}{{{suffix}}}"


metrics = Metrics()
