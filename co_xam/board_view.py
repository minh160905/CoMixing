"""Canvas artwork and pointer interaction for the two board geometries."""

from math import floor, hypot
from pathlib import Path
import tkinter as tk

from .board import (
    FILES, RIVER, SQUARES, WESTERN_PALACE, WK, WQ, WR, WB, WN, WP, XK, XR, XC, XN, XE, XA, XP, square,
)

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
CHESS_COLORS = ("white", "black")
XIANGQI_COLORS = ("red", "black")
PIECE_SIZES = range(24, 129, 4)
PIECE_ATLASES = {
    "white": Path(__file__).with_name("assets") / "western-pieces.png",
    "black": Path(__file__).with_name("assets") / "western-pieces-black.png",
}
PIECE_ATLAS = PIECE_ATLASES["white"]
EAST_RED_MARKS = {XK: "帥", XR: "車", XC: "炮", XN: "馬", XE: "相", XA: "仕", XP: "兵"}
EAST_BLACK_MARKS = {XK: "將", XR: "車", XC: "砲", XN: "馬", XE: "象", XA: "士", XP: "卒"}
EAST_MARKS = EAST_RED_MARKS
EAST_PALETTES = {
    "red": {
        "marks": EAST_RED_MARKS,
        "shadow": "#946747",
        "fill": "#f7dfb4",
        "outline": "#722e27",
        "ring": "#b76a4f",
        "ink": "#762822",
    },
    "black": {
        "marks": EAST_BLACK_MARKS,
        "shadow": "#7c6550",
        "fill": "#eee4cf",
        "outline": "#1e2724",
        "ring": "#586862",
        "ink": "#161d1b",
    },
}


def valid_piece_colors(chess_color, xiangqi_color):
    return (
        chess_color in CHESS_COLORS
        and xiangqi_color in XIANGQI_COLORS
        and not (chess_color == "black" and xiangqi_color == "black")
    )


class BoardView(tk.Canvas):
    def __init__(self, parent, on_pick, on_grab, on_cancel_premove, ui_font, chinese_font,
                 on_inspect_threat=None):
        super().__init__(parent, background=STAGE, highlightthickness=0, takefocus=True)
        self.on_pick = on_pick
        self.on_grab = on_grab
        self.on_cancel_premove = on_cancel_premove
        self.on_inspect_threat = on_inspect_threat
        self.ui_font = ui_font
        self.chinese_font = chinese_font
        self._piece_atlases = {}
        self._piece_images = {}
        self.board = None
        self.displayed = None
        self.flipped = False
        self.chess_color = "white"
        self.xiangqi_color = "red"
        self.threat_source = None
        self.threat_targets = frozenset()
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

    def _mirror_x(self):
        return self.flipped and self.chess_color == "black"

    def show_position(self, board, selection, targets, last_move, check, candidates, *,
                      projected=None, premoves=(), show_targets=True,
                      flipped=False, chess_color="white", xiangqi_color="red",
                      threat_source=None, threat_targets=frozenset()):
        next_mirror = flipped and chess_color == "black"
        if self.displayed is not None and (
            self.displayed[0] != board.key or self.flipped != flipped or self._mirror_x() != next_mirror
        ):
            self.cancel_gestures()
        self.board = board
        self.cells = board.cells if projected is None else projected
        self.grabbable = candidates
        self.clickable = candidates | targets
        self.configure(cursor="hand2" if self._drag_point is not None else "")
        state = (
            board.key, selection, targets, last_move, check, premoves,
            show_targets, projected is not None, flipped, chess_color, xiangqi_color,
            threat_source, threat_targets,
        )
        if state == self.displayed:
            return
        self.displayed = state
        self.selection = selection
        self.targets = targets
        self.last_move = last_move
        self.check = check
        self.premoves = premoves
        self.show_targets = show_targets
        self.flipped = flipped
        self.chess_color = chess_color
        self.xiangqi_color = xiangqi_color
        self.threat_source = threat_source
        self.threat_targets = threat_targets
        self.redraw()

    def point(self, sq):
        row, col = divmod(sq, FILES)
        mirror_x = self._mirror_x()
        if row < RIVER:
            disp_col = 7 - col if mirror_x else col
            disp_row = 3 - row if self.flipped else row
            return self.left + (disp_col + .5) * self.unit, self.chess_top + (disp_row + .5) * self.unit
        disp_col = 8 - col if mirror_x else col
        disp_row = 8 - row if self.flipped else row - RIVER
        base_y = self.xq_top if self.flipped else self.bank
        return self.left + disp_col * self.unit, base_y + disp_row * self.unit

    def _at(self, x, y):
        if not hasattr(self, "unit"):
            return None
        mirror_x = self._mirror_x()
        col = (x - self.left) / self.unit
        if 0 <= col < 8 and self.chess_top <= y < self.chess_top + 4 * self.unit:
            disp_row = floor((y - self.chess_top) / self.unit)
            disp_col = floor(col)
            return square(3 - disp_row if self.flipped else disp_row, 7 - disp_col if mirror_x else disp_col)
        base_y = self.xq_top if self.flipped else self.bank
        row = (y - base_y) / self.unit
        if -.47 <= col <= 8.47 and -.46 <= row <= 4.47:
            disp_row = floor(row + .5)
            disp_col = floor(col + .5)
            return square(8 - disp_row if self.flipped else RIVER + disp_row, 8 - disp_col if mirror_x else disp_col)
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
            if not (state & (_SHIFT | _CONTROL | _ALT)) and self.on_inspect_threat is not None:
                if self.on_inspect_threat(origin):
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
        right = left + 8 * unit
        edge_top = (height - 10.19 * unit) / 2
        edge_bottom = edge_top + 10.19 * unit
        edge_left, edge_right = left - .67 * unit, right + .67 * unit
        if not self.flipped:
            chess_top = self.chess_top = edge_top + .51 * unit
            river_top = chess_top + 4 * unit
            river_bottom = self.bank = river_top + .86 * unit
            xq_top = self.xq_top = river_bottom
            xq_bottom = xq_top + 4 * unit
        else:
            xq_top = self.xq_top = edge_top + .82 * unit
            river_top = xq_top + 4 * unit
            river_bottom = self.chess_top = river_top + .86 * unit
            self.bank = xq_top
            chess_top = self.chess_top
            xq_bottom = river_top
        self.top = chess_top

        self.create_rectangle(edge_left + 3, edge_top + 5, edge_right + 3, edge_bottom + 5,
                              fill="#101a18", outline="")
        self.create_rectangle(edge_left, edge_top, edge_right, edge_bottom,
                              fill=FRAME, outline="#0f1916", width=1)
        self.create_rectangle(edge_left + 3, edge_top + 3, edge_right - 3, edge_bottom - 3,
                              outline="#526a5e", width=1)

        coord_font = (self.ui_font, -max(11, int(unit * .205)), "bold")
        coord_color = "#f0e7d4"
        for disp_row in range(4):
            y = chess_top + disp_row * unit
            rank_label = str(5 + disp_row) if self.flipped else str(8 - disp_row)
            self.create_text(left - .33 * unit, y + .5 * unit,
                             text=rank_label, fill=coord_color, font=coord_font)
            for disp_col in range(8):
                x = left + disp_col * unit
                color = "#e7ddbc" if (disp_row + disp_col) % 2 == 0 else "#779582"
                self.create_rectangle(x, y, x + unit, y + unit, fill=color, outline="")
        mirror_x = self._mirror_x()
        file_labels = "hgfedcba" if mirror_x else "abcdefgh"
        file_y = chess_top + 4 * unit + .25 * unit if self.flipped else chess_top - .25 * unit
        for disp_col, label in enumerate(file_labels):
            self.create_text(left + (disp_col + .5) * unit, file_y,
                             text=label, fill=coord_color, font=coord_font)

        if self.board.balanced:
            x1, y1 = self.point(min(WESTERN_PALACE))
            x2, y2 = self.point(max(WESTERN_PALACE))
            edge = .49 * unit
            self.create_rectangle(min(x1, x2) - edge, min(y1, y2) - edge,
                                  max(x1, x2) + edge, max(y1, y2) + edge,
                                  outline="#225679", width=max(2, .038 * unit), tags=("western-palace",))

        self.create_rectangle(left, river_top, right, river_bottom, fill="#244a50", outline="")
        shore_line_y = river_bottom - 1 if self.flipped else river_top + 1
        self.create_line(left, shore_line_y, right, shore_line_y, fill="#759d99")
        for row in (.29, .57):
            y = river_top + row * unit
            for start, end in ((.52, 3.0), (5.0, 7.48)):
                self.create_line(
                    left + start * unit, y, left + (start + .55) * unit, y - .08 * unit,
                    left + (end - .55) * unit, y + .08 * unit, left + end * unit, y,
                    fill="#527b7e", smooth=True,
                )
        self.create_text((left + right) / 2, river_top + .43 * unit, text="SÔNG",
                         fill="#f4e3b7", font=(self.ui_font, -max(12, int(unit * .24)), "bold"))

        xq_bg_top = xq_top - .44 * unit if self.flipped else xq_top
        xq_bg_bottom = xq_bottom if self.flipped else xq_bottom + .44 * unit
        self.create_rectangle(left - .40 * unit, xq_bg_top, right + .40 * unit, xq_bg_bottom,
                              fill="#dcb482", outline="")
        grid = "#795638"
        xq_file_y = xq_top - .62 * unit if self.flipped else xq_bottom + .62 * unit
        for disp_col in range(9):
            x = left + disp_col * unit
            self.create_line(x, xq_top, x, xq_bottom, fill=grid)
            col_label = str(disp_col + 1) if mirror_x else str(9 - disp_col)
            self.create_text(x, xq_file_y, text=col_label, fill=coord_color, font=coord_font)
        for disp_row in range(5):
            y = xq_top + disp_row * unit
            self.create_line(left, y, right, y, fill=grid, width=1.4 if disp_row in (0, 4) else 1)
            row_label = str(disp_row + 1) if self.flipped else str(5 - disp_row)
            self.create_text(left - .52 * unit, y, text=row_label, fill=coord_color, font=coord_font)
        palace_y1 = xq_top if self.flipped else xq_top + 2 * unit
        palace_y2 = xq_top + 2 * unit if self.flipped else xq_bottom
        for start, end in ((3, 5), (5, 3)):
            self.create_line(left + start * unit, palace_y1, left + end * unit, palace_y2, fill=grid)

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
        if self.threat_source is not None:
            self._mark(self.threat_source, "#cf3d38", .465, "#f3c2bc", 3)
        for sq, color in self.highlights.items():
            outline, fill = _ANNOTATION_COLORS[color]
            if sq in (self.selection, self.check, self.threat_source):
                fill = ""
            self._mark(sq, outline, .47, fill, 3)

        dragged = self._left_start[0] if self._drag_point is not None else None
        for sq in SQUARES:
            piece = self.cells[sq]
            if piece and sq != dragged:
                self._piece(*self.point(sq), piece)
        if self.show_targets:
            self._draw_targets()
        if self.threat_targets:
            self._draw_threats()
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

    def _draw_threats(self):
        unit = self.unit
        real_cells = self.board.cells
        for sq in self.threat_targets:
            x, y = self.point(sq)
            if real_cells[sq]:
                self._disc(x, y, unit * .46, outline="#fff4e6", width=max(4, unit * .078))
                self._disc(x, y, unit * .46, outline="#cf322d", width=max(2.5, unit * .048))
            else:
                self._disc(x, y, unit * .31, outline="#d4453a", width=max(1.8, unit * .032), dash=(4, 3))
                self._disc(x, y, unit * .115, fill="#d4453a", outline="#fff4e6", width=1.4)

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

    def western_image(self, piece, pixels, color=None):
        color = self.chess_color if color is None else color
        size = min(PIECE_SIZES, key=lambda candidate: abs(candidate - pixels))
        key = color, piece, size
        if key not in self._piece_images:
            atlas = self._piece_atlases.get(color)
            if atlas is None:
                atlas = self._piece_atlases[color] = tk.PhotoImage(master=self, file=PIECE_ATLASES[color])
            x = WEST_PIECES.index(piece) * size
            y = sum(range(PIECE_SIZES.start, size, PIECE_SIZES.step))
            image = tk.PhotoImage(master=self, width=size, height=size)
            self.tk.call(image, "copy", atlas, "-from", x, y, x + size, y + size)
            self._piece_images[key] = image
        return self._piece_images[key]

    def _piece(self, x, y, piece, tags=()):
        unit = self.unit
        if piece in WEST_PIECES:
            self.create_image(x, y, image=self.western_image(piece, unit * .93, self.chess_color), tags=tags)
        else:
            palette = EAST_PALETTES[self.xiangqi_color]
            radius = unit * .384
            self._disc(x + .02 * unit, y + .06 * unit, radius, fill=palette["shadow"], outline="", tags=tags)
            self._disc(x, y, radius, fill=palette["fill"], outline=palette["outline"],
                       width=max(1.5, .04 * unit), tags=tags)
            self._disc(x, y, radius * .83, outline=palette["ring"], tags=tags)
            self.create_text(x, y - .012 * unit, text=palette["marks"][piece], fill=palette["ink"],
                             font=(self.chinese_font, -max(16, int(unit * .47)), "bold"), tags=tags)
