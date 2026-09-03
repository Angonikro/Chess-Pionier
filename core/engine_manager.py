from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import os
import json
import chess.engine


@dataclass
class EngineEntry:
    path: str
    name: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = os.path.basename(self.path)


class EngineManager:
    """Engine configuration and process lifecycle.

    Selecting/discovering an engine never starts it. A process is created only
    when play()/analyse() is actually requested.
    """

    def __init__(self, engine_path: Optional[str] = None, *args: Any, **kwargs: Any):
        self.engine_path: Optional[str] = engine_path
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self._running = False
        self.engines: list[EngineEntry] = []
        self._config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "engines.json",
        )
        self.discover_engines()
        self.load_saved_engines()
        if engine_path:
            self.set_engine(engine_path)

    @property
    def is_running(self) -> bool:
        return self.engine is not None and self._running

    def discover_engines(self, directories=None):
        """Discover executable engine files without launching them."""
        if directories is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            directories = [
                os.path.join(base, "engines"),
                os.path.join(base, "engine"),
                os.path.join(base, "bin"),
            ]

        found = []
        for directory in directories:
            if not os.path.isdir(directory):
                continue
            for name in sorted(os.listdir(directory)):
                path = os.path.join(directory, name)
                if not os.path.isfile(path):
                    continue
                low = name.lower()
                if low.endswith((".md", ".txt", ".json", ".png", ".jpg", ".py", ".dll", ".so")):
                    continue
                if os.access(path, os.X_OK) or low.endswith((".exe", ".bin", ".sh", ".elf")):
                    found.append(EngineEntry(path=path))
        self.engines = found
        return list(self.engines)

    def load_saved_engines(self) -> None:
        """Restore selected engine entries from disk; never starts a process."""
        try:
            with open(self._config_path, "r", encoding="utf-8") as fh:
                saved = json.load(fh)
            if not isinstance(saved, list):
                return
            for item in saved:
                if isinstance(item, dict):
                    path = item.get("path")
                    name = item.get("name") or (os.path.basename(path) if path else "")
                else:
                    path = item
                    name = os.path.basename(path) if path else ""
                if path and os.path.isfile(path) and not self.exists(path):
                    self.engines.append(EngineEntry(path=path, name=name))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

    def save_engines(self) -> None:
        """Persist configured engine entries; never starts an engine."""
        try:
            data = [{"name": e.name, "path": e.path} for e in self.engines]
            with open(self._config_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def add(self, name: str, path: Optional[str] = None):
        """Add an engine configuration without starting it.

        UI compatibility: add(name, path).
        """
        actual_path = path if path is not None else name
        actual_name = name if path is not None else ""
        entry = EngineEntry(path=actual_path, name=actual_name)
        if not any(e.path == entry.path for e in self.engines):
            self.engines.append(entry)
            self.save_engines()
        return entry

    def exists(self, path: str) -> bool:
        return any(e.path == path for e in self.engines)

    def remove(self, row_or_entry):
        """Remove a configured engine without touching unrelated processes."""
        try:
            if isinstance(row_or_entry, int):
                if 0 <= row_or_entry < len(self.engines):
                    entry = self.engines.pop(row_or_entry)
                    self.save_engines()
                else:
                    return
            else:
                path = getattr(row_or_entry, "path", row_or_entry)
                entry = next((e for e in self.engines if e.path == path), None)
                if entry:
                    self.engines.remove(entry)
                    self.save_engines()
                else:
                    return
            if getattr(entry, "path", None) == self.engine_path:
                self.stop()
                self.engine_path = None
        except Exception:
            pass

    def set_engine(self, path: Optional[str]) -> None:
        if path != self.engine_path:
            self.stop()
        self.engine_path = path
        if path and not any(e.path == path for e in self.engines):
            self.add(os.path.basename(path), path)

    def load(self, path: Optional[str]) -> None:
        self.set_engine(path)

    def configure(self, path: Optional[str]) -> None:
        self.set_engine(path)

    def start(self) -> Optional[chess.engine.SimpleEngine]:
        if self.engine is not None and self._running:
            return self.engine
        if not self.engine_path:
            return None
        self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
        self._running = True
        return self.engine

    def _start_engine_if_needed(self):
        return self.start()

    def play(self, board, *args: Any, **kwargs: Any):
        engine = self.start()
        if engine is None:
            return None
        return engine.play(board, *args, **kwargs)

    def analyse(self, board, *args: Any, **kwargs: Any):
        engine = self.start()
        if engine is None:
            return None
        return engine.analyse(board, *args, **kwargs)

    def analysis(self, board, *args: Any, **kwargs: Any):
        return self.analyse(board, *args, **kwargs)

    def best_move(self, board, *args: Any, **kwargs: Any):
        result = self.play(board, *args, **kwargs)
        return getattr(result, "move", result)

    def stop(self):
        engine = self.engine
        self.engine = None
        self._running = False
        if engine is None:
            return
        try:
            engine.close()
        except Exception:
            try:
                engine.quit()
            except Exception:
                pass

    def shutdown_all(self) -> None:
        """Application shutdown: stop only processes that are actually running."""
        self.stop()

    def quit(self):
        self.stop()

    def close(self):
        self.stop()

    def shutdown(self):
        self.stop()
