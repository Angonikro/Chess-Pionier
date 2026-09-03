from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QPainter, QImage
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QWidget
import chess
from pathlib import Path

PIECE_SETS = {
    "Staunton": {},
    "Elegant": {},
    "Modern": {},
    "Wood": {},
    "Tournament": {},
}

BOARD_THEMES = {
    "Klassisches Grün": ("#eeeed2", "#769656", "#d8a93e", "#c8c45b"),
    "Holz": ("#f0d9b5", "#b58863", "#d9a441", "#c9a65b"),
    "Blau": ("#dbe5f1", "#4f6f8f", "#e0ad3c", "#a9bdcf"),
    "Schiefer": ("#d5d8dc", "#59636e", "#d5a83b", "#9fa8b2"),
    "Wald": ("#e3e7cf", "#5b7650", "#d4a83b", "#a6b57a"),
}

BOARD_SIZE = 640
SQUARE_SIZE = BOARD_SIZE // 8
PIECE_CODES = {"K":"K","Q":"Q","R":"R","B":"B","N":"N","P":"P"}

class Square(QLabel):
    clicked = Signal(int)
    def __init__(self, square, square_size):
        super().__init__()
        self.square=square
        self.square_size=square_size
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(square_size, square_size)
        self.setSizePolicy(QSizePolicy.Policy.Fixed,QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton: self.clicked.emit(self.square)
        super().mousePressEvent(event)

class ChessBoardWidget(QWidget):
    square_clicked=Signal(int)
    def __init__(self, size=BOARD_SIZE, interactive=True):
        super().__init__()
        self.board_size = int(size)
        self.square_size = max(1, self.board_size // 8)
        self.interactive = interactive
        self.setFixedSize(self.square_size * 8, self.square_size * 8)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.grid=QGridLayout(self); self.grid.setSpacing(0); self.grid.setContentsMargins(0,0,0,0)
        self.grid.setSizeConstraint(QGridLayout.SizeConstraint.SetFixedSize)
        self.squares={}
        for rank in range(7,-1,-1):
            for file in range(8):
                sq=chess.square(file,rank); w=Square(sq, self.square_size)
                if interactive:
                    w.clicked.connect(self.square_clicked.emit)
                else:
                    w.setCursor(Qt.CursorShape.ArrowCursor)
                self.squares[sq]=w
                self.grid.addWidget(w,7-rank,file)
        self.board=chess.Board(); self.selected=None; self.last_move=None
        self.piece_set="Staunton"; self.board_theme="Klassisches Grün"
        self.refresh()

    def set_board(self,board): self.board=board.copy(); self.refresh()
    def set_selected(self,square): self.selected=square; self.refresh()
    def set_last_move(self,move): self.last_move=move; self.refresh()
    def set_piece_set(self,name):
        if name in PIECE_SETS: self.piece_set=name; self.refresh()
    def set_board_theme(self,name):
        if name in BOARD_THEMES: self.board_theme=name; self.refresh()

    def _piece_pixmap(self, symbol):
        code = symbol.upper()
        side = "white" if symbol.isupper() else "black"
        base = Path(__file__).resolve().parent.parent
        path = base / "assets" / "pieces" / f"{self.piece_set}_{side}_{code}.svg"
        if not path.exists():
            return QPixmap()
        image = QImage(max(8, self.square_size - max(4, self.square_size // 8)),
                       max(8, self.square_size - max(4, self.square_size // 8)),
                       QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(str(path))
        if not renderer.isValid():
            return QPixmap()
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        return QPixmap.fromImage(image)

    def refresh(self):
        light,dark,selected_color,last_color=BOARD_THEMES[self.board_theme]
        for sq,widget in self.squares.items():
            file=chess.square_file(sq); rank=chess.square_rank(sq)
            bg=dark if (file+rank)%2 else light
            if sq==self.selected: bg=selected_color
            elif self.last_move and sq in (self.last_move.from_square,self.last_move.to_square): bg=last_color
            widget.setStyleSheet(f"QLabel{{background:{bg};border:0px;}}")
            piece=self.board.piece_at(sq)
            if piece:
                pix=self._piece_pixmap(piece.symbol())
                widget.setPixmap(pix)
            else:
                widget.clear()
