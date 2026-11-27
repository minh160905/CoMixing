"""Canvas artwork and pointer interaction for the two board geometries."""

from math import floor
import tkinter as tk

from .board import FILES, RIVER, SQUARES, WK, WQ, WR, WB, WN, WP, XK, XR, XC, XN, XE, XA, XP, square

STAGE = "#e9e3d7"
FRAME = "#293c4e"
LEGAL = "#15745f"
CAPTURE = "#982e39"
LAST_MOVE = "#996221"
WEST_MARKS = {WK: "♚", WQ: "♛", WR: "♜", WB: "♝", WN: "♞", WP: "♟"}
EAST_MARKS = {XK: "帥", XR: "車", XC: "炮", XN: "馬", XE: "相", XA: "仕", XP: "兵"}


class BoardView(tk.Canvas):
    def __init__(self, parent, on_pick, ui_font, chess_font, chinese_font):
        super().__init__(parent, background=STAGE, highlightthickness=0)
        self.on_pick = on_pick
        self.ui_font = ui_font
        self.chess_font = chess_font
        self.chinese_font = chinese_font
        self.board = None
        self.displayed = None
        self.clickable = frozenset()
        self.bind("<Configure>", lambda _: self.redraw())
        self.bind("<Button-1>", lambda event: self.on_pick(self._at(event.x, event.y)))
        self.bind("<Motion>", self._hover)
        self.bind("<Leave>", lambda _: self.configure(cursor=""))

    def show_position(self, board, selection, targets, last_move, check, candidates):
        self.board = board
        self.clickable = candidates | targets
        self.configure(cursor="")
        state = (board.key, selection, targets, last_move, check)
        if state == self.displayed:
            return
        self.displayed = state
        self.selection = selection
        self.targets = targets
        self.last_move = last_move
        self.check = check
        self.redraw()

    def point(self, sq):
        row, col = divmod(sq, FILES)
        if row < RIVER:
            return self.left + (col + .5) * self.unit, self.top + (row + .5) * self.unit
        return self.left + col * self.unit, self.bank + (row - RIVER) * self.unit

    def _at(self, x, y):
        if not hasattr(self, "unit"):
            return None
        col = (x - self.left) / self.unit
        if 0 <= col < 8 and self.top <= y < self.top + 4 * self.unit:
            return square(floor((y - self.top) / self.unit), floor(col))
        row = (y - self.bank) / self.unit
        if -.47 <= col <= 8.47 and -.46 <= row <= 4.47:
            return square(RIVER + floor(row + .5), floor(col + .5))
        return None

    def _hover(self, event):
        cursor = "hand2" if self._at(event.x, event.y) in self.clickable else ""
        if cursor != self.cget("cursor"):
            self.configure(cursor=cursor)

    def redraw(self):
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        if self.board is None or min(width, height) < 120:
            return

        unit = self.unit = min((width - 28) / 9.34, (height - 25) / 10.19)
        left = self.left = (width - 8 * unit) / 2
        top = self.top = (height - 10.19 * unit) / 2 + .51 * unit
        right = left + 8 * unit
        shore = top + 4 * unit
        bank = self.bank = shore + .86 * unit
        bottom = bank + 4 * unit
        edge_left, edge_right = left - .67 * unit, right + .67 * unit
        edge_top, edge_bottom = top - .51 * unit, bottom + .82 * unit
        self.create_rectangle(edge_left + 3, edge_top + 5, edge_right + 3, edge_bottom + 5,
                              fill="#c9c1b2", outline="")
        self.create_rectangle(edge_left, edge_top, edge_right, edge_bottom,
                              fill=FRAME, outline="#213343", width=1)
        self.create_rectangle(edge_left + 3, edge_top + 3, edge_right - 3, edge_bottom - 3,
                              outline="#62717b", width=1)

        coord_font = (self.ui_font, -max(11, int(unit * .205)), "bold")
        coord_color = "#f0e7d4"
        for row in range(4):
            y = top + row * unit
            self.create_text(left - .33 * unit, y + .5 * unit,
                             text=str(8 - row), fill=coord_color, font=coord_font)
            for col in range(8):
                x = left + col * unit
                color = "#eae1ca" if (row + col) % 2 == 0 else "#9eaead"
                self.create_rectangle(x, y, x + unit, y + unit, fill=color, outline="")
        for col, label in enumerate("abcdefgh"):
            self.create_text(left + (col + .5) * unit, top - .25 * unit,
                             text=label, fill=coord_color, font=coord_font)

        self.create_rectangle(left, shore, right, bank, fill="#304f63", outline="")
        self.create_line(left, shore + 1, right, shore + 1, fill="#a0b4b8")
        for row in (.29, .57):
            y = shore + row * unit
            for start, end in ((.52, 3.0), (5.0, 7.48)):
                self.create_line(
                    left + start * unit, y, left + (start + .55) * unit, y - .08 * unit,
                    left + (end - .55) * unit, y + .08 * unit, left + end * unit, y,
                    fill="#6c8795", smooth=True,
                )
        self.create_text((left + right) / 2, shore + .43 * unit, text="SÔNG",
                         fill="#f4e3b7", font=(self.ui_font, -max(12, int(unit * .24)), "bold"))

        self.create_rectangle(left - .40 * unit, bank, right + .40 * unit, bottom + .44 * unit,
                              fill="#ebd4ad", outline="")
        grid = "#856648"
        for col in range(9):
            x = left + col * unit
            self.create_line(x, bank, x, bottom, fill=grid)
            self.create_text(x, bottom + .62 * unit, text=str(9 - col), fill=coord_color, font=coord_font)
        for row in range(5):
            y = bank + row * unit
            self.create_line(left, y, right, y, fill=grid, width=1.4 if row in (0, 4) else 1)
            self.create_text(left - .52 * unit, y, text=str(5 - row), fill=coord_color, font=coord_font)
        for start, end in ((3, 5), (5, 3)):
            self.create_line(left + start * unit, bank + 2 * unit, left + end * unit, bottom, fill=grid)

        if self.last_move is not None:
            for sq in (self.last_move.src, self.last_move.dst):
                self._mark(sq, LAST_MOVE, .435, "#f6dba1")
        if self.selection is not None:
            self._mark(self.selection, LEGAL, .46, "#bce1ce", 3)
        if self.check is not None:
            self._mark(self.check, CAPTURE, .405, "#efb1a9", 3)

        for sq in SQUARES:
            piece = self.board.cells[sq]
            if piece:
                self._piece(sq, piece)
        for sq in self.targets:
            x, y = self.point(sq)
            if self.board.cells[sq]:
                self._disc(x, y, unit * .46, outline="#fff6e3", width=max(4, unit * .075))
                self._disc(x, y, unit * .46, outline=CAPTURE, width=max(2, unit * .042))
            else:
                self._disc(x, y, unit * .119, fill=LEGAL, outline="#f7f4e1", width=1.5)

    def _mark(self, sq, outline, radius, fill, width=2):
        x, y = self.point(sq)
        size = self.unit * radius
        if sq // FILES < RIVER:
            self.create_rectangle(x - size, y - size, x + size, y + size,
                                  fill=fill, outline=outline, width=width)
        else:
            self._disc(x, y, size, fill=fill, outline=outline, width=width)

    def _disc(self, x, y, radius, **style):
        self.create_oval(x - radius, y - radius, x + radius, y + radius, **style)

    def _piece(self, sq, piece):
        x, y = self.point(sq)
        unit = self.unit
        if piece in WEST_MARKS:
            self.create_oval(x - .285 * unit, y + .295 * unit, x + .285 * unit, y + .345 * unit,
                             fill="#697474", outline="")
            mark = WEST_MARKS[piece]
            glyph = (self.chess_font, -max(22, int(unit * .77)))
            self.create_text(x, y + .018 * unit, text=mark, fill="#e7e6d5", font=glyph)
            self.create_text(x, y - .018 * unit, text=mark, fill="#142a3d", font=glyph)
        else:
            radius = unit * .358
            self._disc(x + .024 * unit, y + .046 * unit, radius, fill="#957054", outline="")
            self._disc(x, y, radius, fill="#f9e4c0", outline="#8b4037", width=max(1.5, .033 * unit))
            self._disc(x, y, radius * .84, outline="#c9966c")
            self.create_text(x, y - .012 * unit, text=EAST_MARKS[piece], fill="#882e29",
                             font=(self.chinese_font, -max(16, int(unit * .445)), "bold"))
