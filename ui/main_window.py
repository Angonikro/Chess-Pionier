from __future__ import annotations
import time
from PySide6.QtCore import Qt, QTimer
import chess
import chess.engine
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QListWidget, QGroupBox, QFileDialog, QMessageBox,
    QSpinBox, QDoubleSpinBox, QFormLayout, QDialog, QDialogButtonBox, QCheckBox, QSlider, QRadioButton
)
from core.engine import UCIEngine
from core.engine_manager import EngineManager
from core.game import ChessGame
from core.audio import AudioManager
from ui.chess_board import ChessBoardWidget, PIECE_SETS, BOARD_THEMES
from version import VERSION


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
        self.preview_timers = {}
        self.build()
        self.refresh_engines()
        self.update_engine_names()
        self.refresh_board()
        self.theme()

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
        new = QPushButton("＋ Neues Spiel"); new.clicked.connect(self.new_game)
        undo = QPushButton("↶ Zurück"); undo.clicked.connect(self.undo)
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
        self.info_button.clicked.connect(self.show_info_dialog)
        self.sound_settings_button = QPushButton("⚙ Sound")
        self.sound_settings_button.clicked.connect(self.open_sound_settings)
        self.update_sound_button()
        buttons.addWidget(new); buttons.addWidget(undo); buttons.addWidget(self.stop); buttons.addWidget(self.sound_button); buttons.addWidget(self.sound_settings_button); buttons.addWidget(self.appearance_button); buttons.addWidget(self.info_button)
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

        right = QVBoxLayout()
        setup = QGroupBox("SPIEL")
        f = QFormLayout(setup)
        self.mode = QComboBox(); self.mode.addItems([
            "Mensch vs. Mensch","Mensch vs. Engine","Engine vs. Mensch","Engine vs. Engine"])
        self.white = QComboBox(); self.black = QComboBox()
        self.seconds = QComboBox()
        self.engine_times = [
            ("2 Sekunden", 2.0),
            ("3 Sekunden", 3.0),
            ("4 Sekunden", 4.0),
            ("5 Sekunden", 5.0),
            ("10 Sekunden", 10.0),
            ("15 Sekunden", 15.0),
            ("30 Sekunden", 30.0),
            ("1 Minute", 60.0),
            ("2 Minuten", 120.0),
            ("3 Minuten", 180.0),
            ("5 Minuten", 300.0),
        ]
        for label, seconds in self.engine_times:
            self.seconds.addItem(label, seconds)
        self.seconds.setCurrentIndex(1)
        f.addRow("Modus", self.mode); f.addRow("Weiß", self.white); f.addRow("Schwarz", self.black); f.addRow("Bedenkzeit", self.seconds)
        self.white.currentTextChanged.connect(self.update_engine_names)
        self.black.currentTextChanged.connect(self.update_engine_names)
        start = QPushButton("▶  SPIEL STARTEN"); start.setObjectName("start"); start.clicked.connect(self.start_game)
        f.addRow(start); right.addWidget(setup)

        mgr = QGroupBox("ENGINE MANAGER")
        ml = QVBoxLayout(mgr); self.engine_list = QListWidget(); ml.addWidget(self.engine_list)
        add = QPushButton("＋ UCI-Engine hinzufügen"); add.clicked.connect(self.add_engine)
        remove = QPushButton("− Entfernen"); remove.clicked.connect(self.remove_engine)
        ml.addWidget(add); ml.addWidget(remove); right.addWidget(mgr, 1)

        ana = QGroupBox("ANALYSE")
        ana.setObjectName("analysisBox")
        ana.setFixedHeight(132)
        al = QVBoxLayout(ana)
        al.setContentsMargins(12, 10, 12, 10)
        al.setSpacing(6)
        self.eval = QLabel("Evaluation  —")
        self.depth = QLabel("Tiefe  —")
        self.pv = QLabel("PV  —")
        self.pv.setWordWrap(True)
        self.pv.setMinimumHeight(42)
        self.pv.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        al.addWidget(self.eval)
        al.addWidget(self.depth)
        al.addWidget(self.pv)
        right.addWidget(ana, 0)
        main.addLayout(right, 0)

    def theme(self):
        self.setStyleSheet("""
        QMainWindow,QWidget{background:#111315;color:#e8eaed}
        QLabel#title{font-size:29px;font-weight:900;letter-spacing:2px}
        QLabel#sub{color:#9aa0a6;font-size:13px}
        QLabel#gameStatus{color:#d8d8d8;font-size:15px;font-weight:800;padding:6px 2px}
        QGroupBox{border:1px solid #30353a;border-radius:12px;margin-top:12px;padding:12px;font-weight:700}
        QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 5px}
        QPushButton,QComboBox,QSpinBox,QDoubleSpinBox{background:#202428;border:1px solid #363c42;border-radius:8px;padding:8px}
        QPushButton:hover{background:#2b3136}
        QPushButton#start{background:#769656;border:0;font-weight:800}
        QPushButton#stop{background:#8f3f3f;border:0;font-weight:800}
        QPushButton#sound{background:#555;border:0;font-weight:800}
        QPushButton#sound[soundOn="true"]{background:#4f8f4f;border:0;font-weight:800}
        QListWidget{background:#17191b;border:1px solid #30353a;border-radius:8px}
        QGroupBox#analysisBox{min-height:132px;max-height:132px}
        QGroupBox#thinkingBlack,QGroupBox#thinkingWhite{padding:6px;border-radius:12px}
        QLabel#thinkingLabel{color:#78a64f;font-size:14px;font-weight:900}
        QLabel#thinkingPV{color:#9aa0a6;font-size:11px;min-height:28px}
        QLabel#engineName{color:#e8eaed;font-size:14px;font-weight:900;padding:6px 2px}
        """)

    def update_engine_names(self, *_):
        self.white_engine_name.setText(self.white.currentText() or "Mensch")
        self.black_engine_name.setText(self.black.currentText() or "Mensch")

    def refresh_engines(self):
        self.white.clear(); self.black.clear()
        self.white.addItem("Mensch"); self.black.addItem("Mensch")
        for e in self.manager.engines:
            self.white.addItem(e.name); self.black.addItem(e.name)
        self.refresh_list()

    def refresh_list(self):
        self.engine_list.clear()
        for e in self.manager.engines:
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
        if board.is_checkmate():
            winner = "Weiß" if board.turn == chess.BLACK else "Schwarz"
            message = f"Schachmatt!\n\n{winner} gewinnt."
            self.game_status.setText(f"♔ {message.replace(chr(10), ' ')}")
            self.show_game_over_dialog("Schachmatt", message)
            return True
        if board.is_stalemate():
            message = "Patt – die Partie endet Remis."
            self.game_status.setText("½ " + message)
            self.show_game_over_dialog("Patt", message)
            return True
        if board.is_fivefold_repetition():
            message = "Remis – die Stellung wurde fünfmal wiederholt."
            self.game_status.setText("½ " + message)
            self.show_game_over_dialog("Remis", message)
            return True
        if board.is_seventyfive_moves():
            message = "Remis – die 75-Züge-Regel greift."
            self.game_status.setText("½ " + message)
            self.show_game_over_dialog("Remis", message)
            return True
        if board.is_insufficient_material():
            message = "Remis – unzureichendes Material."
            self.game_status.setText("½ " + message)
            self.show_game_over_dialog("Remis", message)
            return True
        if board.is_check():
            side = "Weiß" if board.turn == chess.WHITE else "Schwarz"
            self.game_status.setText(f"Schach – {side} ist am Zug")
        else:
            side = "Weiß" if board.turn == chess.WHITE else "Schwarz"
            self.game_status.setText(f"{side} ist am Zug")
        return False

    def new_game(self):
        self.game.reset()
        self.selected = None
        self.board.set_last_move(None)
        self.refresh_board()
        self.update_game_status()
        self.audio.play("start")
        self.eval.setText("Evaluation  —"); self.depth.setText("Tiefe  —"); self.pv.setText("PV  —")
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
        self.black_pv.setText("Wird nicht berechnet")
        self.white_pv.setText("Wird nicht berechnet")
        self.black_thinking_label.setText("SCHWARZ")
        self.white_thinking_label.setText("WEISS")

    def undo(self):
        if self.game.undo():
            self.selected = None; self.refresh_board()

    def on_square(self, square):
        if self.mode.currentText() in ("Engine vs. Mensch","Engine vs. Engine"):
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

    def add_engine(self):
        path, _ = QFileDialog.getOpenFileName(self, "UCI-Engine auswählen")
        if not path: return
        if self.manager.exists(path):
            QMessageBox.information(self, "Chess Pionier", "Diese Engine ist bereits gespeichert.")
            return
        name = path.replace("\\","/").split("/")[-1]
        self.manager.add(name, path)
        self.refresh_engines()

    def remove_engine(self):
        row = self.engine_list.currentRow()
        if row >= 0:
            self.manager.remove(row); self.refresh_engines()

    def start_game(self):
        self.new_game()
        self.maybe_engine()

    def selected_engine_path(self, combo):
        name = combo.currentText()
        for e in self.manager.engines:
            if e.name == name: return e.path
        return None

    def maybe_engine(self):
        mode = self.mode.currentText()
        turn = self.game.board.turn
        wants_engine = (mode == "Mensch vs. Engine" and not turn) or (mode == "Engine vs. Mensch" and turn) or mode == "Engine vs. Engine"
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
        label.setText("SCHWARZ ÜBERLEGT…" if color == chess.BLACK else "WEISS ÜBERLEGT…")
        if pv:
            shown = " → ".join(m.uci() for m in pv[:20])
            pv_label.setText("Vorausberechnet: " + shown)
        else:
            pv_label.setText("Engine berechnet…")

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
            label.setText("SCHWARZ" if color == chess.BLACK else "WEISS")
            pv_label.setText("Wird nicht berechnet")
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
            self.depth.setText(f"Tiefe  {info.get('depth')}")

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
        self.eval.setText(f"Evaluation  {pov}" if pov else "Evaluation  —")
        self.depth.setText(f"Tiefe  {info.get('depth','—')}")
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
        dlg.setWindowTitle("Chess Pionier – Brett & Figuren")
        layout = QVBoxLayout(dlg)
        form = QFormLayout()

        pieces = QComboBox()
        pieces.addItems(["Staunton", "Elegant", "Modern", "Wood", "Tournament"])
        idx = pieces.findText(self.appearance.get("piece_set", "Staunton"))
        if idx >= 0: pieces.setCurrentIndex(idx)

        boards = QComboBox()
        boards.addItems(list(BOARD_THEMES.keys()))
        idx = boards.findText(self.appearance.get("board_theme", "Klassisches Grün"))
        if idx >= 0: boards.setCurrentIndex(idx)

        form.addRow("Figurenstil", pieces)
        form.addRow("Brett-Layout", boards)
        layout.addLayout(form)

        info = QLabel("5 Figurenstile und 5 Brett-Layouts. Das Brett bleibt immer exakt quadratisch (640 × 640 px).")
        info.setWordWrap(True)
        layout.addWidget(info)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        def apply():
            self.appearance = {"piece_set": pieces.currentText(), "board_theme": boards.currentText()}
            self.board.set_piece_set(pieces.currentText())
            self.board.set_board_theme(boards.currentText())
            self.save_appearance()

        buttons.accepted.connect(lambda: (apply(), dlg.accept()))
        buttons.rejected.connect(dlg.reject)
        dlg.exec()

    def update_sound_button(self):
        enabled = bool(self.audio.enabled)
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
        dlg.setWindowTitle("Chess Pionier – Sound-Einstellungen")
        dlg.setModal(True)
        dlg.resize(560, 300)
        layout = QVBoxLayout(dlg)
        form = QFormLayout()

        enabled = QCheckBox("Sounds aktivieren")
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
            device.addItem("Systemstandard", "auto")
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

        form.addRow("Sound", enabled)
        form.addRow("Audio-Treiber", driver)
        form.addRow("Ausgabe-Gerät", device)
        volume_row = QHBoxLayout()
        volume_row.addWidget(volume, 1)
        volume_row.addWidget(volume_label)
        form.addRow("Lautstärke", volume_row)
        layout.addLayout(form)

        info = QLabel(
            "Hier werden die echten SDL2-Wiedergabegeräte des Raspberry Pi angezeigt. "
            "Nach einer Änderung wird der Audio-Mixer neu gestartet."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        test = QPushButton("🔊 Test-Sound")
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
        self.game_status.setText("⚠ Engine konnte keinen Zug ausführen")
        QMessageBox.critical(self, "UCI Engine Fehler", message)
