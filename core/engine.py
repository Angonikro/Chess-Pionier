from __future__ import annotations
import chess
import chess.engine


def _safe_engine_shutdown(engine):
    """Best-effort, non-blocking-ish engine cleanup for GUI shutdown."""
    if engine is None:
        return
    try:
        transport = getattr(engine, "transport", None)
        if transport is None:
            transport = getattr(getattr(engine, "protocol", None), "transport", None)
        # python-chess close() shuts down its transport/event loop as soon as possible.
        try:
            engine.close()
        except Exception:
            pass
        # If the underlying process is still alive, terminate it as a last resort.
        proc = getattr(transport, "get_extra_info", lambda *a, **k: None)("subprocess")
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass
    except Exception:
        pass

class UCIEngine:
    """Thin wrapper around python-chess's UCI engine support."""

    def __init__(self, path: str):
        self.path = path
        self.engine: chess.engine.SimpleEngine | None = None
        self.options = {}

    def start(self):
        self.engine = chess.engine.SimpleEngine.popen_uci(self.path)
        self.options = dict(self.engine.options)

    def configure(self, options: dict):
        if self.engine and options:
            valid = {k: v for k, v in options.items() if k in self.engine.options}
            if valid:
                self.engine.configure(valid)

    def analyse(self, board: chess.Board, limit: chess.engine.Limit):
        if not self.engine:
            raise RuntimeError("Engine is not started")
        return self.engine.analyse(board, limit)

    def play(self, board: chess.Board, limit: chess.engine.Limit):
        if not self.engine:
            raise RuntimeError("Engine is not started")
        return self.engine.play(board, limit)

    def quit(self):
        # close() avoids the blocking engine.wait() path during GUI shutdown.
        if self.engine:
            try:
                self.engine.close()
            except Exception:
                pass
            self.engine = None
