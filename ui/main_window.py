from __future__ import annotations
import time
import subprocess
import threading
import queue
from PySide6.QtCore import Qt, QTimer
import chess
import chess.engine
import chess.pgn
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QListWidget, QGroupBox, QFileDialog, QMessageBox,
    QSpinBox, QDoubleSpinBox, QFormLayout, QDialog, QDialogButtonBox, QCheckBox, QSlider, QRadioButton, QPlainTextEdit, QLineEdit, QAbstractButton
)
from core.engine import UCIEngine
from core.engine_manager import EngineManager
from core.game import ChessGame
from core.audio import AudioManager
from ui.chess_board import ChessBoardWidget, PIECE_SETS, BOARD_THEMES
from version import VERSION



def _translate_dialog_buttons(widget, english=False):
    """Translate common Qt dialog buttons without changing dialog geometry."""
    if english:
        translations = {
            "Cancel": "Cancel", "cancel": "Cancel",
            "Save": "Save", "save": "Save",
            "Open": "Open", "open": "Open",
            "Close": "Close", "close": "Close",
            "OK": "OK", "Ok": "OK",
            "Apply": "Apply", "Reset": "Reset",
            "Yes": "Yes", "No": "No",
            "Select": "Select", "Choose": "Choose",
            "Browse": "Browse",
            "Abbrechen": "Cancel", "Speichern": "Save", "Öffnen": "Open",
            "Schließen": "Close", "Übernehmen": "Apply", "Zurücksetzen": "Reset",
            "Ja": "Yes", "Nein": "No", "Auswählen": "Select", "Durchsuchen": "Browse",
        }
    else:
        translations = {
            "Cancel": "Abbrechen", "cancel": "Abbrechen",
            "Save": "Speichern", "save": "Speichern",
            "Open": "Öffnen", "open": "Öffnen",
            "Close": "Schließen", "close": "Schließen",
            "OK": "OK", "Ok": "OK",
            "Apply": "Übernehmen", "Reset": "Zurücksetzen",
            "Yes": "Ja", "No": "Nein",
            "Select": "Auswählen", "Choose": "Auswählen",
            "Browse": "Durchsuchen",
        }
    for button in widget.findChildren(QAbstractButton):
        text = button.text().strip()
        if text in translations:
            button.setText(translations[text])


def _get_open_file_name(parent, title, directory="", filter_text=""):
    dlg = QFileDialog(parent, title, directory, filter_text)
    dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    _translate_dialog_buttons(dlg, getattr(parent, "language", "de") == "en")
    dlg.show()
    _translate_dialog_buttons(dlg, getattr(parent, "language", "de") == "en")
    if dlg.exec() == QDialog.DialogCode.Accepted:
        files = dlg.selectedFiles()
        return (files[0] if files else ""), dlg.selectedNameFilter()
    return "", ""


def _get_save_file_name(parent, title, directory="", filter_text=""):
    dlg = QFileDialog(parent, title, directory, filter_text)
    dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    _translate_dialog_buttons(dlg, getattr(parent, "language", "de") == "en")
    dlg.show()
    _translate_dialog_buttons(dlg, getattr(parent, "language", "de") == "en")
    if dlg.exec() == QDialog.DialogCode.Accepted:
        files = dlg.selectedFiles()
        return (files[0] if files else ""), dlg.selectedNameFilter()
    return "", ""

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

class EngineWorker(QObject):
    result = Signal(object, object)
    info = Signal(object)
    error = Signal(str)

    def __init__(self, path, board, seconds):
        super().__init__()
        self.path, self.board, self.seconds = path, board.copy(), seconds
        self.engine = None
        self.stopping = False
        self.best_info = {}
        self.best_pv = []
        self._last_info_emit = 0.0

    def _valid_pv(self, pv):
        """Return a legal PV prefix from the exact root position."""
        if not pv:
            return []
        test = self.board.copy()
        valid = []
        for move in pv:
            if move not in test.legal_moves:
                break
            valid.append(move)
            test.push(move)
        return valid

    @Slot()
    def run(self):
        try:
            self.engine = UCIEngine(self.path)
            self.engine.start()
            analysis = self.engine.engine.analysis(
                self.board,
                chess.engine.Limit(time=self.seconds),
                info=chess.engine.INFO_ALL
            )
            try:
                for info in analysis:
                    if self.stopping:
                        break
                    current = dict(info or {})
                    pv = self._valid_pv(list(current.get("pv") or []))
                    if pv:
                        # Never allow an invalid/late PV to replace the last
                        # complete legal principal variation.
                        current["pv"] = pv
                        self.best_pv = pv
                        self.best_info = current
                        now = time.monotonic()
                        # Do not flood the Qt GUI with hundreds of UCI info
                        # packets per second.  The engine keeps calculating at
                        # full speed; the GUI receives a smooth snapshot.
                        if now - self._last_info_emit >= 0.20:
                            self._last_info_emit = now
                            self.info.emit(current)
                    elif current.get("score") is not None:
                        now = time.monotonic()
                        if now - self._last_info_emit >= 0.20:
                            self._last_info_emit = now
                            self.info.emit(current)
            finally:
                try:
                    analysis.stop()
                except Exception:
                    pass

            if not self.stopping:
                if self.best_pv:
                    result_info = dict(self.best_info)
                    result_info["pv"] = list(self.best_pv)
                    self.result.emit(self.best_pv[0], result_info)
                else:
                    self.error.emit("Die Engine hat keinen gültigen Zug geliefert.")
        except Exception as e:
            if not self.stopping:
                self.error.emit(str(e))
        finally:
            if self.engine:
                self.engine.quit()
            self.engine = None

    def stop_now(self):
        self.stopping = True
        if self.engine and self.engine.engine:
            try:
                self.engine.engine.close()
            except Exception:
                pass

class PGNAnalysisDialog(QDialog):
    close_requested = Signal()
    def closeEvent(self, event):
        self.close_requested.emit()
        if self.property("allow_close"):
            event.accept()
        else:
            event.ignore()


class PGNAnalysisWorker(QObject):
    """PGN analyzer.

    Runs the UCI engine in a plain Python worker thread, not a QThread.
    This avoids destroying a QThread/Qt worker while the engine transport
    is still active. The worker owns the subprocess from start to shutdown.
    """
    progress = Signal(int, int, object)
    finished = Signal(bool, str)

    def __init__(self, path, boards, seconds):
        super().__init__()
        self.path = path
        self.boards = [b.copy() for b in boards]
        self.seconds = float(seconds)
        self._stop = threading.Event()
        self.proc = None
        self.lines = queue.Queue()
        self.reader = None

    def request_stop(self):
        self._stop.set()
        proc = self.proc
        if proc is not None:
            # Interrupt the current UCI search without touching Qt objects.
            try:
                if proc.stdin:
                    proc.stdin.write("stop\n")
                    proc.stdin.flush()
            except Exception:
                pass

    def _send(self, text):
        if self.proc is None or self.proc.stdin is None:
            return
        try:
            self.proc.stdin.write(text + "\n")
            self.proc.stdin.flush()
        except Exception:
            pass

    def _start_engine(self):
        self.proc = subprocess.Popen(
            [self.path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

        def reader():
            try:
                for line in self.proc.stdout:
                    self.lines.put(line.strip())
            except Exception:
                pass

        self.reader = threading.Thread(target=reader, daemon=True)
        self.reader.start()

        self._send("uci")
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline and not self._stop.is_set():
            try:
                line = self.lines.get(timeout=0.05)
            except queue.Empty:
                continue
            if line == "uciok":
                self._send("isready")
                break

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not self._stop.is_set():
            try:
                if self.lines.get(timeout=0.05) == "readyok":
                    return True
            except queue.Empty:
                pass
        return not self._stop.is_set()

    def _shutdown_engine(self):
        """Called only by the Python analysis thread."""
        proc = self.proc
        self.proc = None
        if proc is None:
            return

        try:
            if proc.stdin:
                try:
                    proc.stdin.write("quit\n")
                    proc.stdin.flush()
                except Exception:
                    pass

            # Never leave the GUI waiting for engine cleanup.
            proc.wait(timeout=2.0)
        except Exception:
            try:
                proc.terminate()
                proc.wait(timeout=1.0)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=1.0)
                except Exception:
                    pass

        for stream in (proc.stdin, proc.stdout, proc.stderr):
            try:
                if stream:
                    stream.close()
            except Exception:
                pass

    def _parse_info(self, line):
        parts = line.split()
        if not parts or parts[0] != "info":
            return None

        info = {}
        try:
            if "depth" in parts:
                info["depth"] = int(parts[parts.index("depth") + 1])
        except Exception:
            pass

        try:
            if "score" in parts:
                i = parts.index("score")
                kind = parts[i + 1]
                val = int(parts[i + 2])
                info["score"] = ("mate", val) if kind == "mate" else ("cp", val)
        except Exception:
            pass

        if "pv" in parts:
            i = parts.index("pv")
            info["pv"] = parts[i + 1:]
        return info

    @Slot()
    def run(self):
        stopped = False
        message = "Analyse abgeschlossen"
        try:
            if not self._start_engine():
                stopped = True
                message = "Gestoppt"
                return

            total = len(self.boards)
            for number, board in enumerate(self.boards, 1):
                if self._stop.is_set():
                    stopped = True
                    message = "Gestoppt"
                    break

                self._send("ucinewgame")
                self._send("isready")
                ready = False
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline and not self._stop.is_set():
                    try:
                        if self.lines.get(timeout=0.05) == "readyok":
                            ready = True
                            break
                    except queue.Empty:
                        pass

                if self._stop.is_set():
                    stopped = True
                    message = "Gestoppt"
                    break

                if not ready:
                    message = f"Engine nicht bereit bei Stellung {number}."
                    break

                self._send("position fen " + board.fen())
                self._send(f"go movetime {max(50, int(self.seconds * 1000))}")

                best = None
                latest = {}
                deadline = time.monotonic() + self.seconds + 5.0

                while time.monotonic() < deadline:
                    if self._stop.is_set():
                        stopped = True
                        message = "Gestoppt"
                        break
                    try:
                        line = self.lines.get(timeout=0.05)
                    except queue.Empty:
                        continue

                    if line.startswith("info "):
                        parsed = self._parse_info(line)
                        if parsed:
                            latest = parsed
                    elif line.startswith("bestmove"):
                        parts = line.split()
                        if len(parts) >= 2:
                            best = parts[1]
                        break

                if stopped:
                    break

                if not best:
                    message = f"Keine gültige Engine-Antwort bei Stellung {number}."
                    break

                latest["bestmove"] = best
                self.progress.emit(number, total, latest)

        except Exception as exc:
            if self._stop.is_set():
                stopped = True
                message = "Gestoppt"
            else:
                message = str(exc)
        finally:
            self._shutdown_engine()
            self.finished.emit(stopped, message)


class PGNAnalysisBridge(QObject):
    """Queues worker signals safely into the Qt GUI thread."""
    progress_ready = Signal(int, int, object)
    finished_ready = Signal(bool, str)

    @Slot(int, int, object)
    def forward_progress(self, n, total, info):
        self.progress_ready.emit(n, total, info)

    @Slot(bool, str)
    def forward_finished(self, stopped, message):
        self.finished_ready.emit(stopped, message)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess Pionier")
        self.resize(1360, 860)
        self.manager = EngineManager()
        self.audio = AudioManager()
        self.appearance = self.load_appearance()
        self.game = ChessGame()
        self.selected = None
        self.worker_thread = None
        self.worker = None
        self.preview_base = {chess.WHITE: chess.Board(), chess.BLACK: chess.Board()}
        self.preview_pv = {chess.WHITE: [], chess.BLACK: []}
        self.preview_pending_pv = {chess.WHITE: [], chess.BLACK: []}
        self.preview_index = {chess.WHITE: 0, chess.BLACK: 0}
        self.loaded_pgn_game = None
        self.played_games = []
        self.current_game_archived = False
        self.loaded_pgn_moves = []
        self.loaded_pgn_index = 0
        self.pgn_white_name = "Weiß"
        self.pgn_black_name = "Schwarz"
        self.pgn_analysis_dialog = None
        self.pgn_analysis_thread = None
        self.pgn_analysis_worker = None
        self.language = self.load_language()
        self.preview_timers = {}
        self.build()
        self.refresh_engines()
        self.update_engine_names()
        self.refresh_board()
        self.theme()
        self.retranslate_ui()

    def build(self):
        root = QWidget(); self.setCentralWidget(root)
        main = QHBoxLayout(root); main.setContentsMargins(18,18,18,18); main.setSpacing(18)

        left = QVBoxLayout()
        title = QLabel("♟  CHESS PIONIER"); title.setObjectName("title")
        sub = QLabel(f"Universal UCI Chess Client  •  v{VERSION}"); sub.setObjectName("sub")
        left.addWidget(title); left.addWidget(sub)
        self.board = ChessBoardWidget()
        self.board.square_clicked.connect(self.on_square)
        self.board.set_piece_set(self.appearance.get("piece_set", "Staunton"))
        self.board.set_board_theme(self.appearance.get("board_theme", "Klassisches Grün"))
        left.addWidget(self.board, 1)
        self.game_status = QLabel("Bereit")
        self.game_status.setObjectName("gameStatus")
        left.addWidget(self.game_status)
        buttons = QHBoxLayout()
        self.new_game_button = QPushButton("＋ Neues Spiel"); self.new_game_button.clicked.connect(self.new_game)
        self.undo_button = QPushButton("↶ Zurück"); self.undo_button.clicked.connect(self.undo)
        self.stop = QPushButton("■ Spiel stoppen")
        self.stop.setObjectName("stop")
        self.stop.setEnabled(False)
        self.stop.clicked.connect(self.stop_game)
        self.sound_button = QPushButton()
        self.sound_button.setObjectName("sound")
        self.sound_button.clicked.connect(self.toggle_sound)
        self.appearance_button = QPushButton("🎨 Brett & Figuren")
        self.appearance_button.clicked.connect(self.open_appearance_settings)
        self.info_button = QPushButton("ℹ Info")
        self.language_button = QPushButton("🌐 Sprache")
        self.language_button.clicked.connect(self.open_language_settings)
        self.info_button.clicked.connect(self.show_info_dialog)
        self.sound_settings_button = QPushButton("⚙ Sound")
        self.sound_settings_button.clicked.connect(self.open_sound_settings)
        self.update_sound_button()
        buttons.addWidget(self.new_game_button); buttons.addWidget(self.undo_button); buttons.addWidget(self.stop); buttons.addWidget(self.sound_button); buttons.addWidget(self.sound_settings_button); buttons.addWidget(self.appearance_button); buttons.addWidget(self.info_button); buttons.addWidget(self.language_button)
        buttons.addStretch()
        left.addLayout(buttons)
        main.addLayout(left, 0)

        # Dedicated name strip: directly beside the main playing board,
        # outside the two preview-board group boxes.
        name_column = QVBoxLayout()
        name_column.setContentsMargins(0, 0, 0, 0)
        name_column.setSpacing(0)
        self.black_engine_name = QLabel("—")
        self.black_engine_name.setObjectName("engineName")
        self.black_engine_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.black_engine_name.setWordWrap(True)
        self.black_engine_name.setMinimumWidth(100)
        self.black_engine_name.setMaximumWidth(125)
        self.white_engine_name = QLabel("—")
        self.white_engine_name.setObjectName("engineName")
        self.white_engine_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.white_engine_name.setWordWrap(True)
        self.white_engine_name.setMinimumWidth(100)
        self.white_engine_name.setMaximumWidth(125)
        name_column.addStretch(2)
        name_column.addWidget(self.black_engine_name)
        name_column.addStretch(3)
        name_column.addWidget(self.white_engine_name)
        name_column.addStretch(2)
        main.addLayout(name_column, 0)

        # Live engine-preview boards. They are deliberately fixed-size and
        # non-interactive, so they cannot interfere with the main chess board.
        preview = QVBoxLayout()
        preview.setSpacing(10)

        black_box = QGroupBox()
        black_box.setObjectName("thinkingBlack")
        black_layout = QVBoxLayout(black_box)
        black_layout.setContentsMargins(10, 8, 10, 10)
        self.black_thinking_label = QLabel("SCHWARZ")
        self.black_thinking_label.setObjectName("thinkingLabel")
        black_layout.addWidget(self.black_thinking_label)
        self.black_preview = ChessBoardWidget(size=320, interactive=False)
        black_layout.addWidget(self.black_preview, 0, Qt.AlignmentFlag.AlignCenter)
        self.black_pv = QLabel("Wird nicht berechnet")
        self.black_pv.setObjectName("thinkingPV")
        self.black_pv.setWordWrap(True)
        black_layout.addWidget(self.black_pv)
        preview.addWidget(black_box)

        white_box = QGroupBox()
        white_box.setObjectName("thinkingWhite")
        white_layout = QVBoxLayout(white_box)
        white_layout.setContentsMargins(10, 8, 10, 10)
        self.white_thinking_label = QLabel("WEISS")
        self.white_thinking_label.setObjectName("thinkingLabel")
        white_layout.addWidget(self.white_thinking_label)
        self.white_preview = ChessBoardWidget(size=320, interactive=False)
        white_layout.addWidget(self.white_preview, 0, Qt.AlignmentFlag.AlignCenter)
        self.white_pv = QLabel("Wird nicht berechnet")
        self.white_pv.setObjectName("thinkingPV")
        self.white_pv.setWordWrap(True)
        white_layout.addWidget(self.white_pv)
        preview.addWidget(white_box)

        # Each side gets its own preview timer. The timer advances through the
        # engine's current principal variation (PV) one ply at a time.
        for color in (chess.WHITE, chess.BLACK):
            timer = QTimer(self)
            timer.setInterval(280)
            timer.timeout.connect(lambda c=color: self.animate_preview(c))
            self.preview_timers[color] = timer

        main.addLayout(preview, 0)

        # Rechte Spalte: SPIEL oben, danach kompakter ENGINE MANAGER,
        # PGN/PARTIE direkt darunter und kompakte ANALYSE unten.
        # Die Boxen berühren sich ohne zusätzliche Abstände.
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        self.setup_box = QGroupBox("SPIEL")
        setup = self.setup_box
        f = QFormLayout(setup)
        self.mode = QComboBox()
        self.mode.addItem("Mensch vs. Mensch", "hvh")
        self.mode.addItem("Mensch vs. Engine", "hve")
        self.mode.addItem("Engine vs. Mensch", "evh")
        self.mode.addItem("Engine vs. Engine", "eve")
        self.white = QComboBox(); self.black = QComboBox()
        self.seconds = QComboBox()
        self.engine_times = [
            ("2 Sekunden", 2.0), ("3 Sekunden", 3.0), ("4 Sekunden", 4.0),
            ("5 Sekunden", 5.0), ("10 Sekunden", 10.0), ("15 Sekunden", 15.0),
            ("30 Sekunden", 30.0), ("1 Minute", 60.0), ("2 Minuten", 120.0),
            ("3 Minuten", 180.0), ("5 Minuten", 300.0),
        ]
        for label, seconds in self.engine_times:
            self.seconds.addItem(label, seconds)
        self.seconds.setCurrentIndex(1)
        self.form_mode_label = QLabel("Modus"); self.form_white_label = QLabel("Weiß"); self.form_black_label = QLabel("Schwarz"); self.form_time_label = QLabel("Bedenkzeit"); self.form_player_label = QLabel("Spieler")
        f.addRow(self.form_mode_label, self.mode); f.addRow(self.form_white_label, self.white)
        f.addRow(self.form_black_label, self.black); f.addRow(self.form_time_label, self.seconds)

        self.white_player_name = QLineEdit()
        self.white_player_name.setPlaceholderText("Name Weiß")
        self.black_player_name = QLineEdit()
        self.black_player_name.setPlaceholderText("Name Schwarz")
        self.white_player_name.setClearButtonEnabled(True)
        self.black_player_name.setClearButtonEnabled(True)
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name_row.addWidget(self.white_player_name)
        name_row.addWidget(self.black_player_name)
        f.addRow(self.form_player_label, name_row)

        self.white.currentTextChanged.connect(self.update_engine_names)
        self.black.currentTextChanged.connect(self.update_engine_names)
        self.white_player_name.textChanged.connect(self.update_engine_names)
        self.black_player_name.textChanged.connect(self.update_engine_names)
        self.start_button = QPushButton("▶  SPIEL STARTEN"); start = self.start_button; start.setObjectName("start"); start.clicked.connect(self.start_game)
        f.addRow(start); setup.setFixedHeight(260); right.addWidget(setup, 0)

        self.engine_manager_box = QGroupBox("ENGINE MANAGER")
        mgr = self.engine_manager_box
        mgr.setObjectName("engineManagerBox")
        ml = QVBoxLayout(mgr)
        ml.setContentsMargins(12, 12, 12, 10)
        ml.setSpacing(8)
        self.engine_list = QListWidget()
        self.engine_list.setMinimumHeight(140)
        self.engine_list.setMaximumHeight(155)
        ml.addWidget(self.engine_list)
        self.add_engine_button = QPushButton("＋ UCI-Engine hinzufügen"); add = self.add_engine_button; add.clicked.connect(self.add_engine)
        self.remove_engine_button = QPushButton("− Entfernen"); remove = self.remove_engine_button; remove.clicked.connect(self.remove_engine)
        ml.addWidget(add); ml.addWidget(remove)
        mgr.setFixedHeight(245)
        right.addWidget(mgr, 0)

        self.pgn_box = QGroupBox("PGN / PARTIE")
        pgn_box = self.pgn_box
        pgn_box.setObjectName("pgnBox")
        pl = QVBoxLayout(pgn_box)
        pl.setContentsMargins(12, 12, 12, 10)
        pl.setSpacing(7)
        pgn_top = QHBoxLayout(); pgn_top.setSpacing(7)
        self.load_pgn_button = QPushButton("PGN laden"); load_btn = self.load_pgn_button; load_btn.clicked.connect(self.load_pgn)
        self.save_pgn_button = QPushButton("PGN speichern"); save_btn = self.save_pgn_button; save_btn.clicked.connect(self.save_pgn)
        pgn_top.addWidget(load_btn); pgn_top.addWidget(save_btn)
        pgn_top.addStretch()
        pl.addLayout(pgn_top)
        nav = QHBoxLayout(); nav.setSpacing(5)
        first = QPushButton("|◀"); first.clicked.connect(lambda: self.navigate_pgn(0))
        prev = QPushButton("◀"); prev.clicked.connect(lambda: self.navigate_pgn(self.loaded_pgn_index - 1))
        nxt = QPushButton("▶"); nxt.clicked.connect(lambda: self.navigate_pgn(self.loaded_pgn_index + 1))
        last = QPushButton("▶|"); last.clicked.connect(lambda: self.navigate_pgn(len(self.loaded_pgn_moves)))
        nav.addWidget(first); nav.addWidget(prev); nav.addWidget(nxt); nav.addWidget(last)
        pl.addLayout(nav)
        pgn_bottom = QHBoxLayout(); pgn_bottom.setSpacing(7)
        self.analyse_button = QPushButton("Analyse"); analyse_btn = self.analyse_button; analyse_btn.clicked.connect(self.analyse_current_position)
        self.pgn_status = QLabel("Keine PGN geladen")
        self.pgn_status.setMinimumHeight(42)
        self.pgn_status.setObjectName("pgnStatus")
        pgn_bottom.addWidget(analyse_btn); pgn_bottom.addWidget(self.pgn_status, 1)
        pl.addLayout(pgn_bottom)
        pgn_box.setFixedHeight(158)
        right.addWidget(pgn_box, 0)

        self.analysis_box = QGroupBox("ANALYSE")
        ana = self.analysis_box
        ana.setObjectName("analysisBox")
        ana.setFixedHeight(108)
        al = QVBoxLayout(ana)
        al.setContentsMargins(12, 10, 12, 8)
        al.setSpacing(4)
        self.eval = QLabel("Evaluation  —")
        self.depth = QLabel("Tiefe  —")
        self.pv = QLabel("PV  —")
        self.pv.setWordWrap(True)
        self.pv.setMaximumHeight(34)
        self.pv.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        al.addWidget(self.eval); al.addWidget(self.depth); al.addWidget(self.pv)
        right.addWidget(ana, 0)

        main.addLayout(right, 0)

    def theme(self):
        self.setStyleSheet("""
        QMainWindow,QWidget{background:#111315;color:#e8eaed}
        QLabel#title{font-size:29px;font-weight:900;letter-spacing:2px}
        QLabel#sub{color:#9aa0a6;font-size:13px}
        QLabel#gameStatus{color:#d8d8d8;font-size:15px;font-weight:800;padding:6px 2px}
        QGroupBox{border:1px solid #30353a;border-radius:12px;margin-top:0px;padding:12px;font-weight:700}
        QGroupBox::title{subcontrol-origin:margin;left:12px;top:4px;padding:0 5px}
        QPushButton,QComboBox,QSpinBox,QDoubleSpinBox{background:#202428;border:1px solid #363c42;border-radius:8px;padding:8px}
        QPushButton:hover{background:#2b3136}
        QPushButton#start{background:#769656;border:0;font-weight:800}
        QPushButton#stop{background:#8f3f3f;border:0;font-weight:800}
        QPushButton#sound{background:#555;border:0;font-weight:800}
        QPushButton#sound[soundOn="true"]{background:#4f8f4f;border:0;font-weight:800}
        QListWidget{background:#17191b;border:1px solid #30353a;border-radius:8px}
        QGroupBox#analysisBox{min-height:108px;max-height:108px}
        QGroupBox#engineManagerBox{min-height:245px;max-height:245px}
        QGroupBox#pgnBox{min-height:158px;max-height:158px}
        QLabel#pgnStatus{color:#9aa0a6;font-size:11px}
        QGroupBox#thinkingBlack,QGroupBox#thinkingWhite{padding:6px;border-radius:12px}
        QLabel#thinkingLabel{color:#78a64f;font-size:14px;font-weight:900}
        QLabel#thinkingPV{color:#9aa0a6;font-size:11px;min-height:28px}
        QLabel#engineName{color:#e8eaed;font-size:14px;font-weight:900;padding:6px 2px}
        """)

    def _player_display_name(self, combo, name_edit, fallback):
        if combo.currentData() == "human" or combo.currentText() in ("Mensch", "Human"):
            name = name_edit.text().strip()
            return name or fallback
        return combo.currentText() or fallback

    def update_engine_names(self, *_):
        human_fallback = self.tr_app("Mensch", "Human")
        self.white_engine_name.setText(self._player_display_name(self.white, self.white_player_name, human_fallback))
        self.black_engine_name.setText(self._player_display_name(self.black, self.black_player_name, human_fallback))
        self.white_player_name.setEnabled(self.white.currentData() == "human" or self.white.currentText() in ("Mensch", "Human"))
        self.black_player_name.setEnabled(self.black.currentData() == "human" or self.black.currentText() in ("Mensch", "Human"))

    def refresh_engines(self):
        self.white.clear(); self.black.clear()
        human_text = "Human" if getattr(self, "language", "de") == "en" else "Mensch"
        self.white.addItem(human_text, "human"); self.black.addItem(human_text, "human")
        for e in sorted(self.manager.engines, key=lambda x: x.name.casefold()):
            self.white.addItem(e.name, e.path); self.black.addItem(e.name, e.path)
        self.refresh_list()

    def refresh_list(self):
        self.engine_list.clear()
        for e in sorted(self.manager.engines, key=lambda x: x.name.casefold()):
            self.engine_list.addItem(f"✓ {e.name}\n  {e.path}")

    def refresh_board(self):
        self.board.set_board(self.game.board)
        self.board.set_selected(self.selected)

    def show_info_dialog(self):
        """Show the client version and project attribution."""
        box = QMessageBox(self)
        box.setWindowTitle("Chess Pionier – Info")
        box.setText(f"<b>Chess Pionier</b><br><br>Version {VERSION}<br><br>By Goldisoft 2026")
        box.setIcon(QMessageBox.Information)
        box.setStandardButtons(QMessageBox.Ok)
        box.setFixedWidth(300)
        box.exec()

    def show_game_over_dialog(self, title, message):
        """Show a clear, centered result dialog for everyone to see."""
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(message)
        box.setIcon(QMessageBox.Information)
        box.setStandardButtons(QMessageBox.Ok)
        box.setModal(True)
        box.exec()

    def update_game_status(self):
        """Show the exact reason when a chess game has ended."""
        board = self.game.board
        t = self.tr_app
        if board.is_checkmate():
            winner = t("Weiß", "White") if board.turn == chess.BLACK else t("Schwarz", "Black")
            message = t(f"Schachmatt!\\n\\n{winner} gewinnt.", f"Checkmate!\\n\\n{winner} wins.")
            self.game_status.setText("♔ " + message.replace(chr(10), " "))
            self.show_game_over_dialog(t("Schachmatt", "Checkmate"), message)
            return True
        if board.is_stalemate():
            message = t("Patt – die Partie endet Remis.", "Stalemate – the game is a draw.")
            self.game_status.setText("½ " + message)
            self.show_game_over_dialog(t("Patt", "Stalemate"), message)
            return True
        if board.is_fivefold_repetition():
            message = t("Remis – die Stellung wurde fünfmal wiederholt.", "Draw – the position was repeated five times.")
            self.game_status.setText("½ " + message)
            self.show_game_over_dialog(t("Remis", "Draw"), message)
            return True
        if board.is_seventyfive_moves():
            message = t("Remis – die 75-Züge-Regel greift.", "Draw – the 75-move rule applies.")
            self.game_status.setText("½ " + message)
            self.show_game_over_dialog(t("Remis", "Draw"), message)
            return True
        if board.is_insufficient_material():
            message = t("Remis – unzureichendes Material.", "Draw – insufficient material.")
            self.game_status.setText("½ " + message)
            self.show_game_over_dialog(t("Remis", "Draw"), message)
            return True
        side = t("Weiß", "White") if board.turn == chess.WHITE else t("Schwarz", "Black")
        self.game_status.setText(
            t(f"Schach – {side} ist am Zug", f"Check – {side} to move")
            if board.is_check() else
            t(f"{side} ist am Zug", f"{side} to move")
        )
        return False

    def new_game(self):
        self._archive_current_game()
        self.loaded_pgn_game = None
        self.loaded_pgn_moves = []
        self.current_game_archived = False
        self.loaded_pgn_index = 0
        self.pgn_white_name = self.tr_app("Weiß", "White"); self.pgn_black_name = self.tr_app("Schwarz", "Black")
        if hasattr(self, "pgn_status"):
            self.pgn_status.setText(self.tr_app("Keine PGN geladen", "No PGN loaded"))
        self.game.reset()
        self.selected = None
        self.board.set_last_move(None)
        self.refresh_board()
        self.update_game_status()
        self.audio.play("start")
        self.eval.setText(f"{self.tr_app('Bewertung', 'Evaluation')}  —"); self.depth.setText(f"{self.tr_app('Tiefe', 'Depth')}  —"); self.pv.setText("PV  —")
        self.black_preview.set_board(self.game.board)
        self.white_preview.set_board(self.game.board)
        self.black_preview.set_last_move(None)
        self.white_preview.set_last_move(None)
        self.preview_pending_pv[chess.WHITE] = []
        self.preview_pending_pv[chess.BLACK] = []
        self.preview_pv[chess.WHITE] = []
        self.preview_pv[chess.BLACK] = []
        self.preview_index[chess.WHITE] = 0
        self.preview_index[chess.BLACK] = 0
        for _timer in self.preview_timers.values():
            _timer.stop()
        self.black_pv.setText(self.tr_app("Wird nicht berechnet", "Not calculated"))
        self.white_pv.setText(self.tr_app("Wird nicht berechnet", "Not calculated"))
        self.black_thinking_label.setText(self.tr_app("SCHWARZ", "BLACK"))
        self.white_thinking_label.setText(self.tr_app("WEISS", "WHITE"))

    def undo(self):
        if self.game.undo():
            self.selected = None; self.refresh_board()

    def on_square(self, square):
        if self.mode.currentData() in ("evh", "eve"):
            pass
        if self.selected is None:
            p = self.game.board.piece_at(square)
            if p and p.color == self.game.board.turn:
                self.selected = square
                self.refresh_board()
            return
        move = chess.Move(self.selected, square)
        # Promotion: default to queen; GUI can later expose a promotion dialog.
        if chess.square_rank(square) in (0,7) and self.game.board.piece_at(self.selected) and self.game.board.piece_at(self.selected).piece_type == chess.PAWN:
            move = chess.Move(self.selected, square, promotion=chess.QUEEN)
        if move in self.game.board.legal_moves:
            capture = self.game.board.is_capture(move)
            self.game.push(move)
            self.board.set_last_move(move)
            self.audio.play("capture" if capture else "move")
            self.selected = None
            self.refresh_board()
            game_over = self.update_game_status()
            if not game_over:
                self.maybe_engine()
        else:
            self.selected = None
            self.refresh_board()

    def _make_pgn_from_current_game(self):
        """Create a PGN from the current live game's complete move stack."""
        board = self.game.board
        if not getattr(board, "move_stack", None):
            return None
        game = chess.pgn.Game.from_board(board)
        game.headers["Event"] = "Chess Pionier"
        game.headers["White"] = self._player_display_name(self.white, self.white_player_name, self.tr_app("Mensch", "Human"))
        game.headers["Black"] = self._player_display_name(self.black, self.black_player_name, self.tr_app("Mensch", "Human"))
        return game

    def _archive_current_game(self):
        """Archive the live game once when starting a new game."""
        if self.loaded_pgn_game is not None or self.current_game_archived:
            return
        game = self._make_pgn_from_current_game()
        if game is not None:
            self.played_games.append(game)
            self.current_game_archived = True

    def save_pgn(self):
        path, _ = _get_save_file_name(self, "PGN speichern", "", "PGN-Dateien (*.pgn);;Alle Dateien (*)")
        if not path:
            return
        # Die Endung .pgn immer automatisch ergänzen, auch wenn der Benutzer
        # im Dateidialog keinen Dateinamen mit .pgn eingegeben hat.
        if not path.lower().endswith(".pgn"):
            path += ".pgn"
        try:
            game = self._make_pgn_from_current_game()
            if game is None:
                QMessageBox.information(self, "Chess Pionier", self.tr_app("Die aktuelle Partie enthält noch keine Züge.", "The current game has no moves yet."))
                return
            with open(path, "w", encoding="utf-8") as f:
                print(game, file=f)
            self.pgn_status.setText(self.tr_app("PGN gespeichert", "PGN saved"))
        except Exception as e:
            QMessageBox.warning(self, "Chess Pionier", f"{self.tr_app('PGN konnte nicht gespeichert werden:', 'PGN could not be saved:')}\n{e}")

    def load_pgn(self):
        path, _ = _get_open_file_name(self, self.tr_app("PGN laden", "Load PGN"), "", "PGN-Dateien (*.pgn);;All files (*)" if self.language == "en" else "PGN-Dateien (*.pgn);;Alle Dateien (*)")
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                game = chess.pgn.read_game(f)
            if game is None: raise ValueError(self.tr_app("Die Datei enthält keine PGN-Partie.", "The file contains no PGN game."))
            self.loaded_pgn_game = game
            self.loaded_pgn_moves = list(game.mainline_moves())
            self.loaded_pgn_index = 0
            self.pgn_white_name = game.headers.get("White", self.tr_app("Weiß", "White")) or self.tr_app("Weiß", "White")
            self.pgn_black_name = game.headers.get("Black", self.tr_app("Schwarz", "Black")) or self.tr_app("Schwarz", "Black")
            self.white_engine_name.setText(self.pgn_white_name)
            self.black_engine_name.setText(self.pgn_black_name)
            self.navigate_pgn(0)
            self.pgn_status.setText(f"{self.tr_app("PGN geladen", "PGN loaded")}\n{self.pgn_white_name} – {self.pgn_black_name}\n{len(self.loaded_pgn_moves)} {self.tr_app("Züge", "moves")}")
        except Exception as e:
            QMessageBox.warning(self, "Chess Pionier", f"{self.tr_app('PGN konnte nicht geladen werden:', 'PGN could not be loaded:')}\n{e}")

    def navigate_pgn(self, index):
        if self.loaded_pgn_game is None: return
        index=max(0,min(int(index),len(self.loaded_pgn_moves)))
        board=self.loaded_pgn_game.board()
        for move in self.loaded_pgn_moves[:index]: board.push(move)
        self.loaded_pgn_index=index; self.game.board=board; self.game.history=[]; self.selected=None
        self.board.set_last_move(self.loaded_pgn_moves[index-1] if index>0 else None)
        self.refresh_board(); self.update_game_status()
        self.eval.setText(f"{self.tr_app('Bewertung', 'Evaluation')}  —"); self.depth.setText(f"{self.tr_app('Tiefe', 'Depth')}  —"); self.pv.setText("PV  —")

    def analyse_current_position(self):
        if self.loaded_pgn_game is None:
            QMessageBox.information(self,"Chess Pionier",self.tr_app("Bitte zuerst eine PGN laden.", "Please load a PGN first.")); return
        if self.pgn_analysis_thread is not None: return
        boards=[]; board=self.loaded_pgn_game.board()
        for move in self.loaded_pgn_moves:
            board.push(move); boards.append(board.copy())
        if not boards:
            QMessageBox.information(self,"Chess Pionier",self.tr_app("Die PGN enthält keine Züge.", "The PGN contains no moves.")); return
        engines=sorted(self.manager.engines,key=lambda x:x.name.casefold())
        if not engines:
            QMessageBox.information(self,"Chess Pionier",self.tr_app("Bitte zuerst eine UCI-Engine hinzufügen.", "Please add a UCI engine first.")); return

        t = self.tr_app
        dialog=PGNAnalysisDialog(self); dialog.setWindowTitle(t("Chess Pionier – PGN analysieren", "Chess Pionier – Analyze PGN")); dialog.setModal(False); dialog.resize(820,620); dialog.setProperty("allow_close", False)
        layout=QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"<b>{self.pgn_white_name}</b> – <b>{self.pgn_black_name}</b>  ·  {len(boards)} {t("Züge", "moves")}"))
        form=QFormLayout(); engine_combo=QComboBox()
        for e in engines: engine_combo.addItem(e.name,e.path)
        form.addRow("Engine",engine_combo)
        time_combo=QComboBox()
        for label,sec in [("0,5 Sekunden",.5),("1 Sekunde",1.0),("2 Sekunden",2.0),("3 Sekunden",3.0),("5 Sekunden",5.0),("10 Sekunden",10.0),("30 Sekunden",30.0)]:
            time_combo.addItem(label if self.language == "de" else label.replace("Sekunden", "seconds").replace("Sekunde", "second"),sec)
        time_combo.setCurrentIndex(1); form.addRow(t("Zeit pro Zug", "Time per move"),time_combo); layout.addLayout(form)
        progress=QLabel(f"0/{len(boards)}"); layout.addWidget(progress)
        result_box=QPlainTextEdit(); result_box.setReadOnly(True); result_box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap); layout.addWidget(result_box,1)
        buttons=QHBoxLayout(); start_btn=QPushButton(t("▶ Analyse starten", "▶ Start analysis")); stop_btn=QPushButton("■ Stop"); close_btn=QPushButton(t("Schließen", "Close")); stop_btn.setEnabled(False)
        buttons.addWidget(start_btn); buttons.addWidget(stop_btn); buttons.addStretch(); buttons.addWidget(close_btn); layout.addLayout(buttons)
        state={"closing":False}

        def on_progress(n,total,info):
            score=info.get('score'); score_text='—'
            if score:
                kind,val=score
                score_text=(f"Matt {val}" if kind=='mate' else f"{val/100:+.2f}")
            depth=info.get('depth','—'); pv=' '.join(info.get('pv',[])[:12]) or '—'
            progress.setText(f"{n}/{total}")
            result_box.appendPlainText(
                f"{t('Zug/Stellung', 'Move/Position')} {n:>3}: "
                f"{t('Bewertung', 'Evaluation')} {score_text:<10} "
                f"{t('Tiefe', 'Depth')} {depth:<3} PV {pv}"
            )
            result_box.verticalScrollBar().setValue(result_box.verticalScrollBar().maximum())

        def on_finished(stopped,message):
            stop_btn.setEnabled(False); engine_combo.setEnabled(True); time_combo.setEnabled(True)
            if stopped: start_btn.setEnabled(True)
            else: start_btn.setEnabled(message != 'Analyse abgeschlossen')
            shown_message = message
            if message == "Analyse abgeschlossen":
                shown_message = t("Analyse abgeschlossen", "Analysis completed")
            elif message == "Gestoppt":
                shown_message = t("Gestoppt", "Stopped")
            result_box.appendPlainText(("\n■ " if stopped else "\n✓ ")+shown_message)
            if state["closing"]:
                dialog.setProperty("allow_close", True)
                dialog.close()

        def start_analysis():
            if self.pgn_analysis_thread is not None:
                return

            start_btn.setEnabled(False)
            stop_btn.setEnabled(True)
            engine_combo.setEnabled(False)
            time_combo.setEnabled(False)
            result_box.clear()
            progress.setText(f"0/{len(boards)}")

            worker = PGNAnalysisWorker(
                engine_combo.currentData(),
                boards,
                time_combo.currentData(),
            )
            self.pgn_analysis_worker = worker

            # The engine lifetime is completely outside Qt's QThread
            # lifecycle. The bridge delivers results back to the GUI thread.
            bridge = PGNAnalysisBridge()
            self.pgn_analysis_bridge = bridge
            bridge.progress_ready.connect(on_progress)
            bridge.finished_ready.connect(on_finished)
            worker.progress.connect(bridge.forward_progress)
            worker.finished.connect(bridge.forward_finished)

            py_thread = threading.Thread(target=worker.run, daemon=True)
            self.pgn_analysis_thread = py_thread

            def done(stopped, message):
                self.pgn_analysis_worker = None
                self.pgn_analysis_thread = None
                self.pgn_analysis_bridge = None

            bridge.finished_ready.connect(done)
            py_thread.start()

        def stop_analysis():
            if self.pgn_analysis_worker:
                stop_btn.setEnabled(False); result_box.appendPlainText(t("Stop angefordert …", "Stop requested …")); self.pgn_analysis_worker.request_stop()

        def close_dialog():
            state["closing"]=True
            if self.pgn_analysis_worker:
                close_btn.setEnabled(False); stop_btn.setEnabled(False); result_box.appendPlainText(t("Analyse wird beendet …", "Analysis is stopping …")); self.pgn_analysis_worker.request_stop()
            else:
                dialog.setProperty("allow_close", True)
                dialog.close()

        start_btn.clicked.connect(start_analysis); stop_btn.clicked.connect(stop_analysis); close_btn.clicked.connect(close_dialog); dialog.close_requested.connect(close_dialog)
        self.pgn_analysis_dialog=dialog; dialog.show(); dialog.raise_(); dialog.activateWindow()

    def add_engine(self):
        path, _ = _get_open_file_name(self, self.tr_app("UCI-Engine auswählen", "Select UCI engine"))
        if not path: return
        if self.manager.exists(path):
            QMessageBox.information(self, "Chess Pionier", "Diese Engine ist bereits gespeichert.")
            return
        name = path.replace("\\","/").split("/")[-1]
        self.manager.add(name, path)
        self.refresh_engines()

    def remove_engine(self):
        row = self.engine_list.currentRow()
        if row < 0:
            return
        items = sorted(self.manager.engines, key=lambda x: x.name.casefold())
        if row < len(items):
            self.manager.remove(items[row])
            self.refresh_engines()

    def start_game(self):
        self.new_game()
        self.maybe_engine()

    def selected_engine_path(self, combo):
        data = combo.currentData()
        if data and data != "human":
            return data
        name = combo.currentText()
        for e in self.manager.engines:
            if e.name == name: return e.path
        return None

    def maybe_engine(self):
        mode = self.mode.currentData()
        turn = self.game.board.turn
        wants_engine = (mode == "hve" and not turn) or (mode == "evh" and turn) or mode == "eve"
        if not wants_engine or self.game.board.is_game_over():
            return
        combo = self.white if turn else self.black
        path = self.selected_engine_path(combo)
        if not path:
            QMessageBox.warning(self, "Chess Pionier", "Für diesen Spieler wurde keine UCI-Engine ausgewählt.")
            return
        self.run_engine(path)

    def run_engine(self, path):
        if self.worker_thread:
            return
        self.stop.setEnabled(True)
        board = self.game.board.copy()
        self.worker_thread = QThread()
        self.worker = EngineWorker(path, board, max(2.0, float(self.seconds.currentData())))
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.result.connect(self.engine_result)
        self.worker.info.connect(self.engine_info)
        self.worker.error.connect(self.engine_error)
        self.show_thinking_board(board, board.turn, True, {})
        self.worker.result.connect(self.worker_thread.quit)
        self.worker.error.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self.clear_worker)
        self.worker_thread.start()

    def clear_worker(self):
        self.worker = None
        self.worker_thread = None
        self.stop.setEnabled(False)

    def _preview_widgets(self, color):
        if color == chess.BLACK:
            return self.black_preview, self.black_thinking_label, self.black_pv
        return self.white_preview, self.white_thinking_label, self.white_pv

    def _render_preview(self, color):
        target, label, pv_label = self._preview_widgets(color)
        base = self.preview_base[color]
        pv = self.preview_pv[color]
        index = min(self.preview_index[color], len(pv))
        preview_board = base.copy()
        last_move = None

        # Rebuild the preview position from the fixed engine root.  This is
        # important: every displayed position represents the complete PV
        # prefix, not just the last move received from the engine.
        for move in pv[:index]:
            if move not in preview_board.legal_moves:
                break
            preview_board.push(move)
            last_move = move

        self.preview_index[color] = preview_board.ply() - base.ply()
        target.set_board(preview_board)
        target.set_last_move(last_move)
        label.setText(self.tr_app("SCHWARZ ÜBERLEGT…", "BLACK THINKING…") if color == chess.BLACK else self.tr_app("WEISS ÜBERLEGT…", "WHITE THINKING…"))
        if pv:
            shown = " → ".join(m.uci() for m in pv[:20])
            pv_label.setText(self.tr_app("Vorausberechnet: ", "Preview: ") + shown)
        else:
            pv_label.setText(self.tr_app("Engine berechnet…", "Engine calculating…"))

    def _set_new_preview_pv(self, color, pv):
        if not pv:
            return
        # The engine can revise the PV while searching. Preserve the already
        # animated prefix when possible; if the new line diverges, rewind only
        # to the common legal prefix instead of jumping to the last move.
        old = self.preview_pv[color]
        current_index = min(self.preview_index[color], len(old))
        common = 0
        limit = min(current_index, len(pv), len(old))
        while common < limit and old[common] == pv[common]:
            common += 1

        if old == pv[:len(old)] and len(pv) >= len(old):
            # Same line, just extended: keep the current animation position.
            pass
        elif old and current_index > common:
            self.preview_index[color] = common

        self.preview_pv[color] = list(pv)
        self._render_preview(color)
        if len(pv) > self.preview_index[color]:
            self.preview_timers[color].start()

    def show_thinking_board(self, board, color, thinking, info=None):
        target, label, pv_label = self._preview_widgets(color)
        timer = self.preview_timers[color]

        if not thinking:
            timer.stop()
            self.preview_pv[color] = []
            self.preview_pending_pv[color] = []
            self.preview_index[color] = 0
            target.set_board(board)
            target.set_last_move(None)
            label.setText(self.tr_app("SCHWARZ", "BLACK") if color == chess.BLACK else self.tr_app("WEISS", "WHITE"))
            pv_label.setText(self.tr_app("Wird nicht berechnet", "Not calculated"))
            return

        # The root position never changes during one engine search.
        if not timer.isActive() and not self.preview_pv[color] and not self.preview_pending_pv[color]:
            self.preview_base[color] = board.copy()
            self.preview_index[color] = 0
            target.set_board(board)
            target.set_last_move(None)

        pv = list((info or {}).get("pv") or [])
        if pv:
            self.preview_pending_pv[color] = pv
            self._set_new_preview_pv(color, pv)

    def animate_preview(self, color):
        pv = self.preview_pv[color]
        if not pv:
            self.preview_timers[color].stop()
            return
        if self.preview_index[color] < len(pv):
            self.preview_index[color] += 1
            self._render_preview(color)
        else:
            self.preview_timers[color].stop()

    def engine_info(self, info):
        if not self.worker:
            return
        # The worker's board is the exact root position for this calculation.
        color = self.worker.board.turn
        self.show_thinking_board(self.worker.board, color, True, info)
        score = (info or {}).get("score")
        if score:
            try:
                pov = score.pov(color)
                self.eval.setText(f"Evaluation  {pov}")
            except Exception:
                pass
        if info and info.get("depth") is not None:
            self.depth.setText(f"{self.tr_app('Tiefe', 'Depth')}  {info.get('depth')}")

    def engine_result(self, move, info):
        if move not in self.game.board.legal_moves:
            return
        capture = self.game.board.is_capture(move)
        self.game.push(move)
        self.board.set_last_move(move)
        self.audio.play("capture" if capture else "move")
        self.selected = None

        score = info.get("score")
        pov = score.pov(self.game.board.turn) if score else None
        self.eval.setText(f"{self.tr_app('Bewertung', 'Evaluation')}  {pov}" if pov else f"{self.tr_app('Bewertung', 'Evaluation')}  —")
        self.depth.setText(f"{self.tr_app('Tiefe', 'Depth')}  {info.get('depth','—')}")
        pv = info.get("pv", [])
        self.pv.setText(
            "PV  " + " ".join(m.uci() for m in pv[:8])
            if pv else "PV  —"
        )
        self.refresh_board()
        self.show_thinking_board(self.game.board, chess.WHITE, False, {})
        self.show_thinking_board(self.game.board, chess.BLACK, False, {})
        game_over = self.update_game_status()

        # The worker thread is still marked as active while this signal is
        # delivered. Queue the next engine turn until the old worker is gone.
        if not game_over:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(50, self.maybe_engine)

    def stop_game(self):
        self.audio.play("stop")
        if self.worker:
            self.worker.stop_now()
        if self.worker_thread:
            self.worker_thread.quit()
        self.stop.setEnabled(False)
        self.show_thinking_board(self.game.board, chess.WHITE, False, {})
        self.show_thinking_board(self.game.board, chess.BLACK, False, {})
    def closeEvent(self, event):
        """Stop active work and let Qt close without SDL teardown."""
        try:
            for timer in getattr(self, "preview_timers", {}).values():
                timer.stop()
            worker = getattr(self, "worker", None)
            if worker is not None:
                worker.stop_now()
            thread = getattr(self, "worker_thread", None)
            if thread is not None:
                thread.quit()
        except Exception:
            pass

        # Do not call pygame.mixer.quit() here. Native SDL teardown is allowed
        # to happen only as part of the process termination path.
        event.accept()

    def load_language(self):
        import configparser
        from pathlib import Path
        cfg = configparser.ConfigParser(); path = Path("data/settings.ini")
        try:
            if path.exists(): cfg.read(path, encoding="utf-8")
        except configparser.Error: pass
        return cfg.get("General", "language", fallback="de") if cfg.has_section("General") else "de"

    def save_language(self):
        import configparser
        from pathlib import Path
        path=Path("data/settings.ini"); cfg=configparser.ConfigParser()
        try:
            if path.exists(): cfg.read(path, encoding="utf-8")
        except configparser.Error: pass
        if not cfg.has_section("General"): cfg.add_section("General")
        cfg.set("General", "language", self.language)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f: cfg.write(f)

    def tr_app(self, de, en):
        return en if self.language == "en" else de

    def open_language_settings(self):
        dlg=QDialog(self); dlg.setWindowTitle(self.tr_app("Chess Pionier – Sprache", "Chess Pionier – Language"))
        lay=QVBoxLayout(dlg); lay.addWidget(QLabel(self.tr_app("Sprache auswählen:", "Select language:")))
        combo=QComboBox(); combo.addItem("Deutsch", "de"); combo.addItem("English", "en"); combo.setCurrentIndex(0 if self.language=="de" else 1); lay.addWidget(combo)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr_app("Übernehmen", "Apply")); buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr_app("Abbrechen", "Cancel")); lay.addWidget(buttons)
        buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
        if dlg.exec()==QDialog.DialogCode.Accepted:
            self.language=combo.currentData(); self.save_language(); self.retranslate_ui()

    def retranslate_ui(self):
        """Apply the selected language without changing the window geometry."""
        en = self.language == "en"
        t = lambda de, english: english if en else de

        self.setWindowTitle("Chess Pionier")
        self.language_button.setText(t("🌐 Sprache", "🌐 Language"))
        # The sound toggle is state-dependent (ON/OFF or AN/AUS), so it must
        # also be refreshed immediately when the language changes.
        self.update_sound_button()
        self.sound_settings_button.setText(t("⚙ Sound", "⚙ Sound"))
        self.appearance_button.setText(t("🎨 Brett & Figuren", "🎨 Board & Pieces"))
        self.info_button.setText(t("ℹ Info", "ℹ Info"))
        self.new_game_button.setText(t("＋ Neues Spiel", "＋ New Game"))
        self.undo_button.setText(t("↶ Zurück", "↶ Undo"))
        self.start_button.setText(t("▶  SPIEL STARTEN", "▶  START GAME"))
        self.stop.setText(t("■ Spiel stoppen", "■ Stop Game"))

        # Keep the existing layout exactly as it is; only translate captions.
        self.setup_box.setTitle(t("SPIEL", "GAME"))
        self.engine_manager_box.setTitle("ENGINE MANAGER")
        self.add_engine_button.setText(t("＋ UCI-Engine hinzufügen", "＋ Add UCI Engine"))
        self.remove_engine_button.setText(t("− Entfernen", "− Remove"))
        self.pgn_box.setTitle(t("PGN / PARTIE", "PGN / GAME"))
        self.load_pgn_button.setText(t("PGN laden", "Load PGN"))
        self.save_pgn_button.setText(t("PGN speichern", "Save PGN"))
        self.analyse_button.setText(t("Analyse", "Analysis"))
        self.analysis_box.setTitle(t("ANALYSE", "ANALYSIS"))

        self.form_mode_label.setText(t("Modus", "Mode"))
        self.form_white_label.setText(t("Weiß", "White"))
        self.form_black_label.setText(t("Schwarz", "Black"))
        self.form_time_label.setText(t("Bedenkzeit", "Think time"))
        self.form_player_label.setText(t("Spieler", "Players"))

        # Mode labels use stable data keys, so English mode selection still
        # drives the same game logic as German mode selection.
        modes = [
            (t("Mensch vs. Mensch", "Human vs. Human"), "hvh"),
            (t("Mensch vs. Engine", "Human vs. Engine"), "hve"),
            (t("Engine vs. Mensch", "Engine vs. Human"), "evh"),
            (t("Engine vs. Engine", "Engine vs. Engine"), "eve"),
        ]
        current_mode = self.mode.currentData()
        self.mode.blockSignals(True)
        self.mode.clear()
        for text, key in modes:
            self.mode.addItem(text, key)
        idx = self.mode.findData(current_mode)
        self.mode.setCurrentIndex(idx if idx >= 0 else 0)
        self.mode.blockSignals(False)

        # Rebuild the player/engine lists in the selected language.
        current_white = self.white.currentData()
        current_black = self.black.currentData()
        self.refresh_engines()
        if current_white:
            idx = self.white.findData(current_white)
            if idx >= 0:
                self.white.setCurrentIndex(idx)
        if current_black:
            idx = self.black.findData(current_black)
            if idx >= 0:
                self.black.setCurrentIndex(idx)

        self.white_player_name.setPlaceholderText(t("Name Weiß", "White player name"))
        self.black_player_name.setPlaceholderText(t("Name Schwarz", "Black player name"))

        times = [
            (t("2 Sekunden", "2 seconds"), 2.0),
            (t("3 Sekunden", "3 seconds"), 3.0),
            (t("4 Sekunden", "4 seconds"), 4.0),
            (t("5 Sekunden", "5 seconds"), 5.0),
            (t("10 Sekunden", "10 seconds"), 10.0),
            (t("15 Sekunden", "15 seconds"), 15.0),
            (t("30 Sekunden", "30 seconds"), 30.0),
            (t("1 Minute", "1 minute"), 60.0),
            (t("2 Minuten", "2 minutes"), 120.0),
            (t("3 Minuten", "3 minutes"), 180.0),
            (t("5 Minuten", "5 minutes"), 300.0),
        ]
        current_time = self.seconds.currentData()
        self.seconds.blockSignals(True)
        self.seconds.clear()
        for label, value in times:
            self.seconds.addItem(label, value)
        if current_time is not None:
            idx = self.seconds.findData(current_time)
            if idx >= 0:
                self.seconds.setCurrentIndex(idx)
        self.seconds.blockSignals(False)

        # Static status labels.
        self.black_thinking_label.setText(t("SCHWARZ", "BLACK"))
        self.white_thinking_label.setText(t("WEISS", "WHITE"))
        if self.game_status.text() in ("Bereit", "Ready"):
            self.game_status.setText(t("Bereit", "Ready"))
        if self.pgn_status.text() in ("Keine PGN geladen", "No PGN loaded"):
            self.pgn_status.setText(t("Keine PGN geladen", "No PGN loaded"))
        if self.black_pv.text() in ("Wird nicht berechnet", "Not calculated"):
            self.black_pv.setText(t("Wird nicht berechnet", "Not calculated"))
        if self.white_pv.text() in ("Wird nicht berechnet", "Not calculated"):
            self.white_pv.setText(t("Wird nicht berechnet", "Not calculated"))

        self.eval.setText(t("Bewertung  —", "Evaluation  —"))
        self.depth.setText(t("Tiefe  —", "Depth  —"))
        self.pv.setText("PV  —")
        self.update_engine_names()

    def load_appearance(self):
        import configparser
        from pathlib import Path
        path = Path("data/settings.ini")
        cfg = configparser.ConfigParser()
        try:
            if path.exists():
                cfg.read(path, encoding="utf-8")
        except configparser.Error:
            pass
        sec = cfg["Appearance"] if "Appearance" in cfg else {}
        return {
            "piece_set": sec.get("piece_set", "Klassisch") if hasattr(sec, "get") else "Klassisch",
            "board_theme": sec.get("board_theme", "Klassisches Grün") if hasattr(sec, "get") else "Klassisches Grün",
        }

    def save_appearance(self):
        import configparser
        from pathlib import Path
        path = Path("data/settings.ini")
        cfg = configparser.ConfigParser()
        try:
            if path.exists():
                cfg.read(path, encoding="utf-8")
        except configparser.Error:
            pass
        if "Appearance" not in cfg:
            cfg["Appearance"] = {}
        cfg["Appearance"]["piece_set"] = self.appearance.get("piece_set", "Staunton")
        cfg["Appearance"]["board_theme"] = self.appearance.get("board_theme", "Klassisches Grün")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".ini.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            cfg.write(f)
        tmp.replace(path)

    def open_appearance_settings(self):
        dlg = QDialog(self)
        en = self.language == "en"
        t = lambda de, english: english if en else de
        dlg.setWindowTitle(t("Chess Pionier – Brett & Figuren", "Chess Pionier – Board & Pieces"))
        layout = QVBoxLayout(dlg)
        form = QFormLayout()

        pieces = QComboBox()
        pieces.addItems(["Staunton", "Elegant", "Modern", "Wood", "Tournament"])
        idx = pieces.findText(self.appearance.get("piece_set", "Staunton"))
        if idx >= 0: pieces.setCurrentIndex(idx)

        boards = QComboBox()
        board_keys = list(BOARD_THEMES.keys())
        board_labels = {
            "Klassisches Grün": t("Klassisches Grün", "Classic Green"),
            "Blau": t("Blau", "Blue"),
            "Braun": t("Braun", "Brown"),
            "Grau": t("Grau", "Gray"),
            "Holz": t("Holz", "Wood"),
        }
        for key in board_keys:
            boards.addItem(board_labels.get(key, key), key)
        idx = boards.findData(self.appearance.get("board_theme", "Klassisches Grün"))
        if idx >= 0: boards.setCurrentIndex(idx)

        form.addRow(t("Figurenstil", "Piece style"), pieces)
        form.addRow(t("Brett-Layout", "Board layout"), boards)
        layout.addLayout(form)

        info = QLabel(t(
            "5 Figurenstile und 5 Brett-Layouts. Das Brett bleibt immer exakt quadratisch (640 × 640 px).",
            "5 piece styles and 5 board layouts. The board always remains exactly square (640 × 640 px)."
        ))
        info.setWordWrap(True)
        layout.addWidget(info)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(t("Abbrechen", "Cancel"))
        layout.addWidget(buttons)

        def apply():
            self.appearance = {"piece_set": pieces.currentText(), "board_theme": boards.currentData()}
            self.board.set_piece_set(pieces.currentText())
            self.board.set_board_theme(boards.currentText())
            self.save_appearance()

        buttons.accepted.connect(lambda: (apply(), dlg.accept()))
        buttons.rejected.connect(dlg.reject)
        dlg.exec()

    def update_sound_button(self):
        enabled = bool(self.audio.enabled)
        if getattr(self, "language", "de") == "en":
            self.sound_button.setText("🔊 ON" if enabled else "🔇 OFF")
        else:
            self.sound_button.setText("🔊 AN" if enabled else "🔇 AUS")
        self.sound_button.setProperty("soundOn", "true" if enabled else "false")
        self.sound_button.style().unpolish(self.sound_button)
        self.sound_button.style().polish(self.sound_button)
        self.sound_button.update()

    def toggle_sound(self):
        self.audio.set_enabled(not self.audio.enabled)
        self.update_sound_button()

    def open_sound_settings(self):
        dlg = QDialog(self)
        t = self.tr_app
        dlg.setWindowTitle(t("Chess Pionier – Sound-Einstellungen", "Chess Pionier – Sound Settings"))
        dlg.setModal(True)
        dlg.resize(560, 300)
        layout = QVBoxLayout(dlg)
        form = QFormLayout()

        enabled = QCheckBox(t("Sounds aktivieren", "Enable sounds"))
        enabled.setChecked(self.audio.enabled)

        driver = QComboBox()
        for name in self.audio.available_drivers():
            driver.addItem(name, name)
        idx = driver.findData(self.audio.driver)
        if idx >= 0:
            driver.setCurrentIndex(idx)

        device = QComboBox()
        device.setEditable(False)

        def load_devices():
            current = self.audio.device
            device.blockSignals(True)
            device.clear()
            device.addItem(t("Systemstandard", "System default"), "auto")
            devices = self.audio.available_devices(driver.currentData())
            for name in devices:
                if name:
                    device.addItem(str(name), str(name))
            idx = device.findData(current)
            device.setCurrentIndex(idx if idx >= 0 else 0)
            device.blockSignals(False)

        driver.currentIndexChanged.connect(load_devices)
        load_devices()

        volume = QSlider(Qt.Orientation.Horizontal)
        volume.setRange(0, 100)
        volume.setValue(int(self.audio.volume * 100))
        volume_label = QLabel(f"{volume.value()} %")
        volume.valueChanged.connect(lambda v: volume_label.setText(f"{v} %"))

        form.addRow(t("Sound", "Sound"), enabled)
        form.addRow(t("Audio-Treiber", "Audio driver"), driver)
        form.addRow(t("Ausgabe-Gerät", "Output device"), device)
        volume_row = QHBoxLayout()
        volume_row.addWidget(volume, 1)
        volume_row.addWidget(volume_label)
        form.addRow(t("Lautstärke", "Volume"), volume_row)
        layout.addLayout(form)

        info = QLabel(
            t("Hier werden die echten SDL2-Wiedergabegeräte des Raspberry Pi angezeigt. "
              "Nach einer Änderung wird der Audio-Mixer neu gestartet.",
              "The actual SDL2 playback devices of the Raspberry Pi are shown here. "
              "The audio mixer is restarted after a change.")
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(t("Abbrechen", "Cancel"))
        test = QPushButton(t("🔊 Test-Sound", "🔊 Test sound"))
        buttons.addButton(test, QDialogButtonBox.ButtonRole.ActionRole)
        layout.addWidget(buttons)
        test.clicked.connect(lambda: self.audio.test())

        def apply():
            self.audio.shutdown()
            self.audio.enabled = enabled.isChecked()
            self.audio.driver = driver.currentData() or "auto"
            self.audio.device = device.currentData() or "auto"
            self.audio.volume = volume.value() / 100.0
            self.audio.save_settings()
            self.update_sound_button()
            if self.audio.enabled:
                self.audio.test()

        buttons.accepted.connect(lambda: (apply(), dlg.accept()))
        buttons.rejected.connect(dlg.reject)
        dlg.exec()

    def engine_error(self, message):
        for color in (chess.WHITE, chess.BLACK):
            self.show_thinking_board(self.game.board, color, False, {})
        self.game_status.setText(t("⚠ Engine konnte keinen Zug ausführen", "⚠ Engine could not make a move"))
        QMessageBox.critical(self, t("UCI-Engine-Fehler", "UCI Engine Error"), message)
