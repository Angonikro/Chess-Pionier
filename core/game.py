from __future__ import annotations
import chess

class ChessGame:
    def __init__(self):
        self.board = chess.Board()
        self.history = []

    def push(self, move: chess.Move):
        if move not in self.board.legal_moves:
            return False
        self.history.append(self.board.fen())
        self.board.push(move)
        return True

    def undo(self):
        if self.history:
            self.board.pop()
            self.history.pop()
            return True
        return False

    def reset(self):
        self.board.reset()
        self.history.clear()
