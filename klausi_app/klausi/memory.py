"""Dauerhaftes Gedächtnis: kurze Notizen, die Klausi sich merkt."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path


class Memory:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write(self, notes: list[dict]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def all(self) -> list[dict]:
        with self._lock:
            return self._read()

    def add(self, text: str) -> int:
        with self._lock:
            notes = self._read()
            notes.append({"text": text.strip(), "created": datetime.now().isoformat(timespec="minutes")})
            self._write(notes)
            return len(notes)

    def remove(self, number: int) -> bool:
        with self._lock:
            notes = self._read()
            if 1 <= number <= len(notes):
                notes.pop(number - 1)
                self._write(notes)
                return True
            return False

    def as_prompt(self) -> str:
        notes = self.all()
        if not notes:
            return "Du hast dir noch nichts gemerkt."
        lines = [f"{i}. {n['text']}" for i, n in enumerate(notes, start=1)]
        return "Das hast du dir gemerkt:\n" + "\n".join(lines)
