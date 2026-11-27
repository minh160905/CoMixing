"""Canvas artwork and pointer interaction for the two board geometries."""

from math import floor, hypot
from pathlib import Path
import tkinter as tk

from .board import FILES, RIVER, SQUARES, WK, WQ, WR, WB, WN, WP, XK, XR, XC, XN, XE, XA, XP, square

STAGE = "#192825"
FRAME = "#243832"
LEGAL = "#15745f"
CAPTURE = "#982e39"
LAST_MOVE = "#996221"
PREMOVE = "#6441a2"
_PREMOVE_FILL = "#e7dcfa"
_ANNOTATION_COLORS = {
    "red": ("#b33e45", "#f1b5af"),
    "amber": ("#a9601a", "#f3d397"),
    "blue": ("#2866a4", "#bcd8f3"),
    "green": ("#1b7654", "#b6dcc6"),
}

# Tk includes Alt in different state bits on Windows and X11.
_SHIFT, _CONTROL, _ALT = 0x1, 0x4, 0x20008
WEST_PIECES = (WK, WQ, WR, WB, WN, WP)
PIECE_SIZES = range(24, 129, 4)
PIECE_ATLAS = Path(__file__).with_name("assets") / "western-pieces.png"
EAST_MARKS = {XK: "帥", XR: "車", XC: "炮", XN: "馬", XE: "相", XA: "仕", XP: "兵"}


class BoardView(tk.Canvas):
    def __init__(self, parent, on_pick, on_grab, on_cancel_premove, ui_font, chinese_font):
        super().__init__(parent, background=STAGE, highlightthickness=0, takefocus=True)
        self.on_pick = on_pick
        self.on_grab = on_grab
        self.on_cancel_premove = on_cancel_premove
        self.ui_font = ui_font
        self.chinese_font = chinese_font
        self._piece_atlas = tk.PhotoImage(master=self, file=PIECE_ATLAS)
        self._piece_images = {}
        self.board = None
        self.displayed = None
        self.clickable = frozenset()
        self.grabbable = frozenset()
        self.highlights = {}
        self.arrows = {}
        self._left_start = None
        self._drag_point = None
        self._right_start = None
        self.bind("<Configure>", lambda _: self.redraw())
        self.bind("<ButtonPress-1>", self._press_left)
        self.bind("<B1-Motion>", self._drag_left)
        self.bind("<ButtonRelease-1>", self._release_left)
        self.bind("<ButtonPress-3>", self._press_right)
        self.bind("<B3-Motion>", self._drag_right)
        self.bind("<ButtonRelease-3>", self._release_right)
        self.bind("<Motion>", self._hover)
        self.bind("<Leave>", lambda _: self.configure(cursor=""))

    def show_position(self, board, selection, targets, last_move, check, candidates, *,
                      projected=None, premoves=(), show_targets=True):
        if self.displayed is not None and self.displayed[0] != board.key:
            self.cancel_gestures()
        self.board = board
        self.cells = board.cells if projected is None else projected
        self.grabbable = candidates
        self.clickable = candidates | targets
        self.configure(cursor="hand2" if self._drag_point is not None else "")
        state = (board.key, selection, targets, last_move, check, premoves, show_targets, projected is not None)
        if state == self.displayed:
            return
        self.displayed = state
        self.selection = selection
        self.targets = targets
        self.last_move = last_move
        self.check = check
        self.premoves = premoves
        self.show_targets = show_targets
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

    def clear_annotations(self):
        if self.highlights or self.arrows:
            self.highlights.clear()
            self.arrows.clear()
            self.redraw()

    def cancel_gestures(self):
        was_dragging = self._drag_point is not None
        self._left_start = self._drag_point = self._right_start = None
        self.delete("arrow-preview")
        if was_dragging:
            self.redraw()

    def _press_left(self, event):
        self.focus_set()
        self.clear_annotations()
        self._left_start = (self._at(event.x, event.y), event.x, event.y)

    def _drag_left(self, event):
        if self._left_start is None:
            return
        sq, x, y = self._left_start
        if sq not in self.grabbable:
            return
        if self._drag_point is None:
            if hypot(event.x - x, event.y - y) < 5:
                return
            self._drag_point = (event.x, event.y)
            self.on_grab(sq)
            self.redraw()
        else:
            x, y = self._drag_point
            self.move("dragged-piece", event.x - x, event.y - y)
            self._drag_point = (event.x, event.y)

    def _release_left(self, event):
        if self._left_start is None:
            return
        dragged = self._drag_point is not None
        self._left_start = self._drag_point = None
        if dragged:
            self.redraw()
        self.on_pick(self._at(event.x, event.y), dragged=dragged)

    @staticmethod
    def _annotation_color(state, arrow=False):
        if state & _SHIFT:
            return "green"
        if state & _ALT:
            return "blue"
        if state & _CONTROL:
            return "red" if arrow else "amber"
        return "amber" if arrow else "red"

    def _press_right(self, event):
        self.focus_set()
        self._right_start = (self._at(event.x, event.y), event.state)

    def _drag_right(self, event):
        self.delete("arrow-preview")
        if self._right_start is None:
            return
        origin, state = self._right_start
        target = self._at(event.x, event.y)
        if origin is not None and target is not None and origin != target:
            color = _ANNOTATION_COLORS[self._annotation_color(state, arrow=True)][0]
            self._arrow(origin, target, color, "arrow-preview")

    def _release_right(self, event):
        self.delete("arrow-preview")
        if self._right_start is None:
            return
        origin, state = self._right_start
        self._right_start = None
        target = self._at(event.x, event.y)
        if origin is None or target is None:
            return
        if origin == target:
            if self.on_cancel_premove(origin):
                return
            annotations, key = self.highlights, origin
        else:
            annotations, key = self.arrows, (origin, target)
        color = self._annotation_color(state, arrow=origin != target)
        if annotations.get(key) == color:
            del annotations[key]
        else:
            annotations[key] = color
        self.redraw()

    def _hover(self, event):
        cursor = "hand2" if self._at(event.x, event.y) in self.clickable else ""
        if cursor != self.cget("cursor"):
            self.configure(cursor=cursor)

    def redraw(self):
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        if self.board is None or min(width, height) < 120:
            return

        unit = self.unit = min((width - 24) / 9.34, (height - 16) / 10.19)
        left = self.left = (width - 8 * unit) / 2
        top = self.top = (height - 10.19 * unit) / 2 + .51 * unit
        right = left + 8 * unit
        shore = top + 4 * unit
        bank = self.bank = shore + .86 * unit
        bottom = bank + 4 * unit
        edge_left, edge_right = left - .67 * unit, right + .67 * unit
        edge_top, edge_bottom = top - .51 * unit, bottom + .82 * unit
        self.create_rectangle(edge_left + 3, edge_top + 5, edge_right + 3, edge_bottom + 5,
                              fill="#101a18", outline="")
        self.create_rectangle(edge_left, edge_top, edge_right, edge_bottom,
                              fill=FRAME, outline="#0f1916", width=1)
        self.create_rectangle(edge_left + 3, edge_top + 3, edge_right - 3, edge_bottom - 3,
                              outline="#526a5e", width=1)

        coord_font = (self.ui_font, -max(11, int(unit * .205)), "bold")
        coord_color = "#f0e7d4"
        for row in range(4):
            y = top + row * unit
            self.create_text(left - .33 * unit, y + .5 * unit,
                             text=str(8 - row), fill=coord_color, font=coord_font)
            for col in range(8):
                x = left + col * unit
                color = "#e7ddbc" if (row + col) % 2 == 0 else "#779582"
                self.create_rectangle(x, y, x + unit, y + unit, fill=color, outline="")
        for col, label in enumerate("abcdefgh"):
            self.create_text(left + (col + .5) * unit, top - .25 * unit,
                             text=label, fill=coord_color, font=coord_font)

        self.create_rectangle(left, shore, right, bank, fill="#244a50", outline="")
        self.create_line(left, shore + 1, right, shore + 1, fill="#759d99")
        for row in (.29, .57):
            y = shore + row * unit
            for start, end in ((.52, 3.0), (5.0, 7.48)):
                self.create_line(
                    left + start * unit, y, left + (start + .55) * unit, y - .08 * unit,
                    left + (end - .55) * unit, y + .08 * unit, left + end * unit, y,
                    fill="#527b7e", smooth=True,
                )
        self.create_text((left + right) / 2, shore + .43 * unit, text="SÔNG",
                         fill="#f4e3b7", font=(self.ui_font, -max(12, int(unit * .24)), "bold"))

        self.create_rectangle(left - .40 * unit, bank, right + .40 * unit, bottom + .44 * unit,
                              fill="#dcb482", outline="")
        grid = "#795638"
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
        for move in self.premoves:
            for sq in (move.src, move.dst):
                self._mark(sq, PREMOVE, .445, _PREMOVE_FILL, 2)
        if self.selection is not None:
            if self.cells is self.board.cells:
                self._mark(self.selection, LEGAL, .46, "#bce1ce", 3)
            else:
                self._mark(self.selection, PREMOVE, .46, _PREMOVE_FILL, 3)
        if self.check is not None:
            self._mark(self.check, CAPTURE, .405, "#efb1a9", 3)
        for sq, color in self.highlights.items():
            outline, fill = _ANNOTATION_COLORS[color]
            if sq in (self.selection, self.check):
                fill = ""
            self._mark(sq, outline, .47, fill, 3)

        dragged = self._left_start[0] if self._drag_point is not None else None
        for sq in SQUARES:
            piece = self.cells[sq]
            if piece and sq != dragged:
                self._piece(*self.point(sq), piece)
        if self.show_targets:
            self._draw_targets()
        for (src, dst), color in self.arrows.items():
            self._arrow(src, dst, _ANNOTATION_COLORS[color][0])
        if dragged is not None:
            self._piece(*self._drag_point, self.cells[dragged], tags=("dragged-piece",))

    def _draw_targets(self):
        unit = self.unit
        preview = self.cells is not self.board.cells
        for sq in self.targets:
            x, y = self.point(sq)
            if not preview and self.cells[sq]:
                self._disc(x, y, unit * .46, outline="#fff6e3", width=max(4, unit * .075))
                self._disc(x, y, unit * .46, outline=CAPTURE, width=max(2, unit * .042))
            elif preview:
                self._disc(x, y, unit * .43, outline=PREMOVE, width=2, dash=(3, 3))
            else:
                self._disc(x, y, unit * .119, fill=LEGAL, outline="#f7f4e1", width=1.5)

    def _arrow(self, src, dst, color, tag="annotation-arrow"):
        x1, y1 = self.point(src)
        x2, y2 = self.point(dst)
        dx, dy = x2 - x1, y2 - y1
        distance = hypot(dx, dy)
        unit = self.unit
        start, end = .24 * unit / distance, .31 * unit / distance
        self.create_line(
            x1 + dx * start, y1 + dy * start, x2 - dx * end, y2 - dy * end,
            fill=color, width=max(3, .11 * unit), capstyle=tk.ROUND, arrow=tk.LAST,
            arrowshape=tuple(max(4, value * unit) for value in (.20, .25, .11)), tags=(tag,),
        )

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

    def western_image(self, piece, pixels):
        size = min(PIECE_SIZES, key=lambda candidate: abs(candidate - pixels))
        key = piece, size
        if key not in self._piece_images:
            x = WEST_PIECES.index(piece) * size
            y = sum(range(PIECE_SIZES.start, size, PIECE_SIZES.step))
            image = tk.PhotoImage(master=self, width=size, height=size)
            self.tk.call(image, "copy", self._piece_atlas, "-from", x, y, x + size, y + size)
            self._piece_images[key] = image
        return self._piece_images[key]

    def _piece(self, x, y, piece, tags=()):
        unit = self.unit
        if piece in WEST_PIECES:
            self.create_image(x, y, image=self.western_image(piece, unit * .93), tags=tags)
        else:
            radius = unit * .384
            self._disc(x + .02 * unit, y + .06 * unit, radius, fill="#946747", outline="", tags=tags)
            self._disc(x, y, radius, fill="#f7dfb4", outline="#722e27", width=max(1.5, .04 * unit), tags=tags)
            self._disc(x, y, radius * .83, outline="#b76a4f", tags=tags)
            self.create_text(x, y - .012 * unit, text=EAST_MARKS[piece], fill="#762822",
                             font=(self.chinese_font, -max(16, int(unit * .47)), "bold"), tags=tags)
