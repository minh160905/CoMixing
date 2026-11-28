"""Tk interface and game controls for Akbar VS HanXin."""

from math import hypot
import logging
from queue import Empty, Queue
from threading import Event, Thread
import tkinter as tk
from tkinter import font, ttk

from . import GAME_NAME
from .board import (
    CANNON_UNLOCK_PLY, CHESS, XIANGQI, EMPTY, SIDE, SIDE_NAMES, PIECE_NAMES, SIZE, SQUARES,
    CHECKMATE, STALEMATE, REPETITION, NO_PROGRESS,
    WK, WQ, WR, WB, WN, WP, XK, XR, XC, XN, XE, XA, XP,
    Board, coordinates, square, validate_custom_position,
)
from .board_view import (
    BoardView, EAST_PALETTES, STAGE, LEGAL, CAPTURE, LAST_MOVE, PREMOVE,
    WEST_PIECES, valid_piece_colors,
)
from .premove import MAX_PREMOVES, PremoveQueue, possible_moves
from .search import EXPERT_SECONDS, Search

APP_BG = "#101917"
PAPER = "#1c2b27"
BORDER = "#385047"
INK = "#f4efdf"
MUTED = "#b9c7bd"
NAV = "#182521"
NAV_CONTROL = "#2a3d35"
NAV_TEXT = "#faf1d9"
GOLD = "#f0ca83"
SOFT = "#2a3d35"
HOVER = "#3a5248"
WEST = "#ade0c5"
WEST_TINT = "#295046"
EAST = "#ffad95"
EAST_TINT = "#53362e"

REASONS = {
    CHECKMATE: "Chiếu hết",
    STALEMATE: "Hết nước đi hợp lệ",
    REPETITION: "Thế cờ lặp lại 3 lần",
    NO_PROGRESS: "50 lượt mỗi bên không bắt quân hoặc đi Tốt",
}

RULES = (
    ("Bắt đầu", "Cờ tướng đi trước. Chọn quân rồi chọn một điểm được đánh dấu để đi."),
    ("Cổ điển và Cân bằng", "Ở bộ luật Cân bằng, Vua cờ vua chỉ đi trong cung 4 × 3, "
     "từ cột c đến f và từ hàng 8 đến 6. Đường viền xanh trên bàn đánh dấu cung Vua. "
     "Vua có thể nhập thành xa nếu đủ điều kiện."),
    ("Các nước riêng của Cân bằng", "Tượng cờ tướng đi chéo hai bước, được qua sông và bỏ chặn mắt. "
     "Sĩ được ra khỏi cung bằng nước ngang hoặc dọc một bước, kể cả qua sông. Sĩ chỉ đi chéo trên "
     "đường kẻ trong cung. Xe cờ vua đi tối đa hai bước khi xuất phát ở phần cờ tướng. "
     "Tốt cờ vua đến hàng cuối không phong cấp và từ đó chỉ đi hoặc ăn ngang một điểm."),
    ("Qua sông", "Một nước vượt sông dừng ở bờ đến. Ô cờ vua ứng với hai giao điểm "
     "cờ tướng kề nó. Đường kẻ ngoài cùng chỉ có một ô cờ vua tương ứng."),
    ("Hậu, Tượng và Tốt", "Hậu và Tượng cờ vua đi tối đa hai bước khi xuất phát "
     "trên phần cờ tướng. Khi qua sông, Tốt cờ vua chỉ tiến thẳng đến giao điểm trống. "
     "Trước hàng cuối phần cờ tướng, Tốt cờ vua đi thẳng và ăn chéo về phía trước. "
     "Ở Cổ điển, Tốt cờ vua phong cấp ở hàng cuối. Tốt cờ tướng được đi hoặc ăn ngang trên phần cờ vua."),
    ("Mã và cung Tướng", "Mã hai bên bị chặn chân khi xuất phát trên phần cờ tướng. "
     "Trên phần cờ vua, Mã nhảy tự do. Tướng ở trong cung và được đi chéo một điểm "
     "theo đường kẻ nối tâm cung với góc. Ở Cổ điển, Sĩ ở trong cung và Tượng cờ tướng ở phần sân nhà."),
    ("Pháo", "Pháo cần đúng một quân làm ngòi khi ăn quân. Trong ba lượt đầu "
     "của bên cờ tướng, ngòi phải là quân cờ tướng."),
    ("Nhập thành và lộ mặt Tướng", "Vua cờ vua được nhập thành theo luật cờ vua. "
     "Nước đi của bất kỳ bên nào làm Vua và Tướng lộ mặt đều không hợp lệ."),
    ("Kết thúc ván", "Chiếu hết thắng ván. Ván hòa khi bên đến lượt hết nước hợp lệ "
     "mà không bị chiếu, thế cờ lặp lại ba lần hoặc có 100 nước liên tiếp không ăn quân và không đi Tốt."),
)


def _font_family(available, choices):
    return next((name for name in choices if name in available), "TkDefaultFont")


class GameApp:
    def __init__(self, root):
        self.root = root
        available = set(font.families(root))
        self.ui_font = _font_family(available, ("Segoe UI", "DejaVu Sans", "Arial"))
        self.heading_font = _font_family(available, ("Georgia", "Cambria", "DejaVu Serif"))
        self.chess_font = _font_family(available, ("Segoe UI Symbol", "DejaVu Sans", "Noto Sans Symbols 2"))
        self.chinese_font = _font_family(available, ("Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "SimSun"))
        root.configure(bg=APP_BG)
        root.title(GAME_NAME)
        root.minsize(790, 630)
        screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
        width, height = min(1180, screen_w - 28), max(630, min(900, screen_h - 105))
        root.geometry(f"{width}x{height}+{max(0, (screen_w - width) // 2)}+{max(0, (screen_h - height - 44) // 2)}")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Escape>", lambda _: self._escape_board())
        root.bind("<Control-z>", lambda _: self.undo())
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)
        self._configure_styles()

        self._build_header()
        body = tk.Frame(root, bg=APP_BG)
        body.grid(row=1, column=0, sticky="nsew", padx=18, pady=16)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        stage = tk.Frame(body, bg=STAGE, highlightbackground=BORDER, highlightthickness=1)
        stage.grid(row=0, column=0, sticky="nsew", padx=(0, 15))
        stage.grid_columnconfigure(0, weight=1)
        stage.grid_rowconfigure(1, weight=1)
        self.seats = {
            CHESS: self._build_seat(stage, CHESS, 0),
            XIANGQI: self._build_seat(stage, XIANGQI, 2),
        }
        self.view = BoardView(stage, self.pick, self.grab, self._cancel_premove_at,
                              self.ui_font, self.chinese_font, self._inspect_threat,
                              self._practice_click, self._practice_drop, self._practice_delete)
        self.view.grid(row=1, column=0, sticky="nsew")
        self._build_legend(stage)

        self.practice_mode = False
        self.practice_cells = None
        self.practice_turn = XIANGQI
        self.practice_brush = WQ
        self.practice_cannon_open = tk.BooleanVar(root, value=True)
        self._palette_drag = None

        panel = tk.Frame(body, bg=APP_BG, width=328)
        panel.grid(row=0, column=1, sticky="ns")
        panel.pack_propagate(False)
        self._build_controls(panel)

        self.balanced = False
        self.saved_games = {}
        self.vs_bot = False
        self.human = CHESS
        self.chess_color = "white"
        self.xiangqi_color = "red"
        self.threat_source = None
        self.think_time = 3
        self.job = None
        self.rules_window = None
        self.options_window = None
        self.promotion_window = None
        self.premoves = PremoveQueue()
        self.enable_premoves = tk.BooleanVar(root, value=True)
        self.show_last_move = tk.BooleanVar(root, value=True)
        self.show_legal_moves = tk.BooleanVar(root, value=True)
        self.displayed_log = None
        self.engine = Search()
        self.new_game()

    def _configure_styles(self):
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        linespace = font.Font(root=self.root, family=self.ui_font, size=9).metrics("linespace")
        style.configure("Moves.Treeview", background=PAPER, fieldbackground=PAPER, foreground=INK,
                        borderwidth=0, relief="flat", rowheight=linespace + 8, font=(self.ui_font, 9))
        style.configure("Moves.Treeview.Heading", background=SOFT, foreground=MUTED,
                        borderwidth=0, padding=(8, 5), relief="flat", font=(self.ui_font, 9, "bold"))
        style.map("Moves.Treeview.Heading", background=[("active", SOFT)])
        style.map("Moves.Treeview", background=[("selected", WEST_TINT)], foreground=[("selected", INK)])
        style.configure("Paper.Vertical.TScrollbar", background=BORDER, troughcolor=PAPER,
                        borderwidth=0, relief="flat", arrowsize=11)

    def _label(self, parent, text, size=10, *, fg=INK, bg=PAPER, bold=False, heading=False, wrap=0):
        family = self.heading_font if heading else self.ui_font
        return tk.Label(parent, text=text, font=(family, size, "bold" if bold else "normal"),
                        fg=fg, bg=bg, anchor="w", justify="left", wraplength=wrap, padx=0, pady=0)

    def _button(self, parent, text, command, *, kind="plain", compact=False):
        normal, foreground, hover = {
            "primary": (GOLD, NAV, "#f5d89f"),
            "nav": (NAV_CONTROL, NAV_TEXT, HOVER),
            "plain": (SOFT, INK, HOVER),
        }[kind]
        button = tk.Button(
            parent, text=text, command=command, relief="flat", borderwidth=0,
            bg=normal, fg=foreground, activebackground=hover, activeforeground=foreground,
            disabledforeground="#a0ada5", font=(self.ui_font, 9 if compact else 10, "bold"),
            padx=9 if compact else 14, pady=4 if compact else 6, highlightthickness=1,
            highlightbackground=parent.cget("bg"), highlightcolor=WEST, takefocus=True,
        )
        button.normal_color = normal
        button.bind("<Enter>", lambda _: self._button_hover(button, True), add="+")
        button.bind("<Leave>", lambda _: self._button_hover(button, False), add="+")
        return button

    @staticmethod
    def _button_hover(button, entered):
        enabled = button.cget("state") != "disabled"
        if entered and enabled:
            button.configure(cursor="hand2", bg=button.cget("activebackground"))
        else:
            button.configure(cursor="", bg=button.normal_color)

    def _build_header(self):
        nav = tk.Frame(self.root, bg=NAV, padx=20, pady=10)
        nav.grid(row=0, column=0, sticky="ew")
        seal = tk.Canvas(nav, width=47, height=47, bg=NAV, highlightthickness=0)
        seal.pack(side="left", padx=(0, 12))
        seal.create_polygon(2, 8, 8, 2, 39, 2, 45, 8, 45, 39, 39, 45, 8, 45, 2, 39,
                            fill=NAV_CONTROL, outline=GOLD)
        seal.create_line(27, 9, 20, 38, fill="#80968a")
        seal.create_text(14, 23, text="♞", fill=NAV_TEXT, font=(self.chess_font, -19))
        seal.create_text(33, 23, text="帥", fill=GOLD, font=(self.chinese_font, -15, "bold"))
        title = tk.Frame(nav, bg=NAV)
        title.pack(side="left")
        self._label(title, GAME_NAME, 23, fg=NAV_TEXT, bg=NAV, bold=True, heading=True).pack(anchor="w")
        self._label(title, "Cờ vua × Cờ tướng", 9, fg="#c4cfd3", bg=NAV).pack(anchor="w")
        self.rules_button = self._button(nav, "Luật chơi", self.show_rules, kind="nav")
        self.rules_button.pack(side="right")
        self.options_button = self._button(nav, "Tùy chọn", self.show_options, kind="nav")
        self.options_button.pack(side="right", padx=(0, 8))
        self.practice_button = self._button(nav, "Phòng tập", self.toggle_practice, kind="nav")
        self.practice_button.pack(side="right", padx=(0, 8))
        self.new_button = self._button(nav, "Ván mới", self.new_game, kind="primary")
        self.new_button.pack(side="right", padx=(0, 8))
        tk.Frame(self.root, bg=BORDER, height=1).grid(row=0, column=0, sticky="sew")

    def _build_seat(self, stage, side, row):
        bar = tk.Frame(stage, bg=PAPER, padx=9, pady=3)
        bar.grid(row=row, column=0, sticky="ew", padx=10, pady=(6, 0))
        west = side == CHESS
        mark, family, color = ("♔", self.chess_font, WEST) if west else ("帥", self.chinese_font, EAST)
        accent = tk.Frame(bar, bg=BORDER, width=3)
        accent.pack(side="left", fill="y", padx=(0, 7))
        mark_label = tk.Label(bar, text=mark, bg=PAPER, fg=color, font=(family, 11, "bold"))
        mark_label.pack(side="left")
        name = self._label(bar, SIDE_NAMES[side], 9, fg=color, bold=True)
        name.pack(side="left", padx=(5, 0))
        status = self._label(bar, "", 9, fg=color, bold=True)
        status.pack(side="right")
        return bar, mark_label, name, status, accent

    def _build_legend(self, stage):
        legend = tk.Frame(stage, bg=STAGE, pady=5)
        legend.grid(row=3, column=0)
        for name, color, shape in (
            ("Nước hợp lệ", LEGAL, "dot"),
            ("Ăn quân", CAPTURE, "ring"),
            ("Nước vừa đi", LAST_MOVE, "box"),
            ("PreMove", PREMOVE, "premove"),
        ):
            item = tk.Frame(legend, bg=STAGE)
            item.pack(side="left", padx=8)
            marker = tk.Canvas(item, width=16, height=16, bg=STAGE, highlightthickness=0)
            marker.pack(side="left", padx=(0, 4))
            if shape == "dot":
                marker.create_oval(4, 4, 12, 12, fill=color, outline="")
            elif shape == "ring":
                marker.create_oval(3, 3, 13, 13, outline=color, width=2)
            else:
                fill = "#e7dcfa" if shape == "premove" else "#f6dba1"
                marker.create_rectangle(3, 3, 13, 13, fill=fill, outline=color)
            self._label(item, name, 9, fg=MUTED, bg=STAGE).pack(side="left")

    @staticmethod
    def _card(parent, padx=12, pady=9):
        return tk.Frame(parent, bg=PAPER, padx=padx, pady=pady,
                        highlightbackground=BORDER, highlightthickness=1)

    def _build_controls(self, panel):
        turn_card = self._card(panel)
        turn_card.pack(fill="x", pady=(0, 9))
        self.turn_icon = tk.Canvas(turn_card, width=44, height=44, bg=PAPER, highlightthickness=0)
        self.turn_icon.pack(side="left", padx=(0, 10))
        self.icon_tile = self.turn_icon.create_rectangle(1, 1, 43, 43, fill=EAST_TINT, outline="")
        self.icon_mark = self.turn_icon.create_text(22, 22, text="", fill=EAST)
        self.icon_piece = self.turn_icon.create_image(22, 22, image=self.view.western_image(WK, 36))
        status = tk.Frame(turn_card, bg=PAPER)
        status.pack(side="left", fill="x", expand=True)
        self.turn_context = self._label(status, "", 9, fg=MUTED, bold=True)
        self.turn_context.pack(anchor="w")
        self.turn_label = self._label(status, "", 17, heading=True, bold=True)
        self.turn_label.pack(anchor="w")
        self.status_label = self._label(status, "", 9, fg=MUTED, wrap=242)
        self.status_label.pack(anchor="w", pady=(2, 0))

        settings = self._card(panel)
        settings.pack(fill="x", pady=(0, 9))
        self.ruleset_buttons = self._options(
            settings, "Bộ luật", (("Cổ điển", False), ("Cân bằng", True)), self.set_ruleset
        )
        self.mode_buttons = self._options(
            settings, "Chế độ chơi", (("Hai người", False), ("Đấu máy", True)), self.set_mode, margin=7
        )
        color_row = tk.Frame(settings, bg=PAPER)
        color_row.pack(fill="x", pady=(7, 0))
        color_row.grid_columnconfigure(0, weight=1, uniform="color_group")
        color_row.grid_columnconfigure(1, weight=1, uniform="color_group")
        chess_color_box = tk.Frame(color_row, bg=PAPER)
        chess_color_box.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        xiangqi_color_box = tk.Frame(color_row, bg=PAPER)
        xiangqi_color_box.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.chess_color_buttons = self._options(
            chess_color_box, "Màu cờ vua", (("Trắng", "white"), ("Đen", "black")), self.set_chess_color
        )
        self.xiangqi_color_buttons = self._options(
            xiangqi_color_box, "Màu cờ tướng", (("Đỏ", "red"), ("Đen", "black")), self.set_xiangqi_color
        )
        self.bot_panel = tk.Frame(settings, bg=PAPER)
        self.side_buttons = self._options(
            self.bot_panel, "Bạn cầm", (("Cờ vua", CHESS), ("Cờ tướng", XIANGQI)), self.set_human, margin=7
        )
        self.time_buttons = self._options(
            self.bot_panel, "Thời gian bot",
            (("1 giây", 1), ("3 giây", 3), ("8 giây", 8), (f"Chuyên gia · {EXPERT_SECONDS} giây", EXPERT_SECONDS)),
            self.set_time, margin=7, columns=2,
        )

        history = self.history_card = self._card(panel, padx=10)
        history.pack(fill="both", expand=True)
        log_header = tk.Frame(history, bg=PAPER)
        log_header.pack(fill="x", padx=2, pady=(0, 6))
        self._label(log_header, "Nước đi", 12, bold=True, heading=True).pack(side="left")
        self.log_count = self._label(log_header, "", 9, fg=MUTED)
        self.log_count.pack(side="right")
        footer = tk.Frame(history, bg=PAPER)
        footer.pack(side="bottom", fill="x", pady=(7, 0))
        self.undo_button = self._button(footer, "↶  Hoàn tác", self.undo)
        self.undo_button.pack(fill="x")
        scrollable = tk.Frame(history, bg=PAPER, highlightbackground=BORDER, highlightthickness=1)
        scrollable.pack(fill="both", expand=True)
        scrollable.grid_columnconfigure(0, weight=1)
        scrollable.grid_rowconfigure(0, weight=1)
        self.log = ttk.Treeview(scrollable, style="Moves.Treeview", show="headings", height=2,
                               columns=("turn", "piece", "notation"), selectmode="browse")
        self.log.grid(row=0, column=0, sticky="nsew")
        self.log.heading("turn", text="Số")
        self.log.heading("piece", text="Quân")
        self.log.heading("notation", text="Di chuyển")
        self.log.column("turn", width=34, minwidth=34, anchor="center", stretch=False)
        self.log.column("piece", width=68, minwidth=64, stretch=False)
        self.log.column("notation", width=153, minwidth=133)
        for side, color in ((CHESS, WEST), (XIANGQI, EAST)):
            self.log.tag_configure(f"{side}-0", background=PAPER, foreground=color)
            self.log.tag_configure(f"{side}-1", background=NAV, foreground=color)
        self.log_scroll = ttk.Scrollbar(scrollable, orient="vertical", command=self.log.yview,
                                        style="Paper.Vertical.TScrollbar")
        self.log_scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=self._on_log_scroll)
        self.empty_log = self._label(scrollable, "Chưa có nước đi", 9, fg=MUTED)
        self.practice_panel = self._build_practice_panel(panel)

    def _build_practice_panel(self, panel):
        card = self._card(panel, padx=10, pady=8)
        self._label(card, "Phòng tập · Tạo thế cờ", 11, bold=True, heading=True).pack(anchor="w")
        self._label(
            card, "Kéo thả quân vào bàn hoặc bấm chọn quân rồi nhấp ô. Kéo ra ngoài hoặc chuột phải để xóa.",
            8, fg=MUTED, wrap=298,
        ).pack(anchor="w", pady=(2, 6))

        self.palette_tiles = {}
        self._label(card, "Quân Cờ vua", 8, fg=WEST, bold=True).pack(anchor="w")
        west_row = tk.Frame(card, bg=PAPER)
        west_row.pack(fill="x", pady=(2, 5))
        for idx, piece in enumerate(WEST_PIECES):
            west_row.grid_columnconfigure(idx, weight=1, uniform="west_pal")
            tile = self._palette_tile(west_row, piece, 40)
            tile.grid(row=0, column=idx, padx=2, sticky="ew")
            self.palette_tiles[piece] = tile

        self._label(card, "Quân Cờ tướng", 8, fg=EAST, bold=True).pack(anchor="w")
        east_row = tk.Frame(card, bg=PAPER)
        east_row.pack(fill="x", pady=(2, 6))
        for idx, piece in enumerate((XK, XR, XC, XN, XE, XA, XP)):
            east_row.grid_columnconfigure(idx, weight=1, uniform="east_pal")
            tile = self._palette_tile(east_row, piece, 36)
            tile.grid(row=0, column=idx, padx=1, sticky="ew")
            self.palette_tiles[piece] = tile

        tools = tk.Frame(card, bg=PAPER)
        tools.pack(fill="x", pady=(0, 6))
        for idx in range(3):
            tools.grid_columnconfigure(idx, weight=1, uniform="ptool")
        self.eraser_button = self._button(tools, "Xóa quân", lambda: self._select_brush(EMPTY), compact=True)
        self.eraser_button.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self._button(tools, "Xóa bàn", self._practice_clear_board, compact=True).grid(
            row=0, column=1, sticky="ew", padx=3
        )
        self._button(tools, "Mặc định", self._practice_reset_default, compact=True).grid(
            row=0, column=2, sticky="ew", padx=(3, 0)
        )

        self.practice_turn_buttons = self._options(
            card, "Bên đi trước", (("Cờ tướng", XIANGQI), ("Cờ vua", CHESS)), self._set_practice_turn
        )
        tk.Checkbutton(
            card, text="Mở khóa ngòi Pháo (bỏ giới hạn 3 lượt đầu)", variable=self.practice_cannon_open,
            command=self._refresh, bg=PAPER, activebackground=PAPER, fg=MUTED, selectcolor=SOFT,
            font=(self.ui_font, 8), anchor="w",
        ).pack(fill="x", pady=(4, 4))

        self.practice_status = self._label(card, "", 8, fg=MUTED, wrap=298)
        self.practice_status.pack(anchor="w", pady=(0, 6))

        actions = tk.Frame(card, bg=PAPER)
        actions.pack(side="bottom", fill="x")
        actions.grid_columnconfigure(0, weight=2)
        actions.grid_columnconfigure(1, weight=1)
        self.practice_start_button = self._button(
            actions, "Chơi từ thế cờ này", self.start_practice_game, kind="primary", compact=True
        )
        self.practice_start_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._button(actions, "Thoát", self.toggle_practice, compact=True).grid(row=0, column=1, sticky="ew")
        return card

    def _palette_tile(self, parent, piece, size):
        tile = tk.Canvas(parent, width=size, height=size, bg=SOFT, highlightthickness=1,
                         highlightbackground=BORDER, cursor="hand2")
        tile.piece = piece
        tile.tile_size = size
        tile.bind("<ButtonPress-1>", lambda e, p=piece: self._palette_press(e, p))
        tile.bind("<B1-Motion>", self._palette_motion)
        tile.bind("<ButtonRelease-1>", self._palette_release)
        tile.bind("<Configure>", lambda _: self._redraw_palette() if self.practice_mode else None)
        return tile

    def _redraw_palette(self):
        palette = EAST_PALETTES[self.xiangqi_color]
        for piece, tile in self.palette_tiles.items():
            selected = self.practice_brush == piece
            tile.configure(bg=WEST_TINT if selected else SOFT,
                           highlightbackground=GOLD if selected else BORDER)
            tile.delete("all")
            w = tile.winfo_width()
            size = w if w > 10 else tile.tile_size
            cx, cy = size / 2, tile.tile_size / 2
            if piece in WEST_PIECES:
                tile.create_image(cx, cy, image=self.view.western_image(piece, 32, self.chess_color))
            else:
                r = 14
                tile.create_oval(cx - r, cy - r, cx + r, cy + r,
                                 fill=palette["fill"], outline=palette["outline"], width=1.6)
                tile.create_text(cx, cy, text=palette["marks"][piece], fill=palette["ink"],
                                 font=(self.chinese_font, -16, "bold"))

    def _palette_press(self, event, piece):
        self._palette_drag = [piece, event.x_root, event.y_root, False]
        self._select_brush(piece)

    def _palette_motion(self, event):
        if self._palette_drag is None:
            return
        piece, sx, sy, dragging = self._palette_drag
        if not dragging and hypot(event.x_root - sx, event.y_root - sy) < 5:
            return
        self._palette_drag[3] = True
        self.view.preview_palette_drag(piece, event.x_root, event.y_root)

    def _palette_release(self, event):
        if self._palette_drag is None:
            return
        piece, _, _, dragging = self._palette_drag
        self._palette_drag = None
        if dragging:
            sq = self.view.drop_palette_piece(event.x_root, event.y_root)
            if sq is not None:
                self._practice_place(sq, piece)

    def toggle_practice(self):
        self._cancel_bot()
        self._clear_plan()
        self.view.clear_annotations()
        if self.practice_mode:
            self.practice_mode = False
        else:
            self.practice_mode = True
            self.practice_cells = self.board.cells.copy()
            self.practice_turn = self.board.turn
        self._refresh()

    def _select_brush(self, piece):
        self.practice_brush = piece
        self._refresh()

    def _set_practice_turn(self, side):
        self.practice_turn = side
        self._refresh()

    def _practice_clear_board(self):
        self.practice_cells = [EMPTY] * SIZE
        self.practice_cells[square(0, 4)] = WK
        self.practice_cells[square(8, 4)] = XK
        self._refresh()

    def _practice_reset_default(self):
        self.practice_cells = Board(balanced=self.balanced).cells.copy()
        self.practice_turn = XIANGQI
        self._refresh()

    def _practice_place(self, sq, piece):
        if not self.practice_mode or sq is None or sq not in SQUARES:
            return
        if piece in (WK, XK):
            for idx, existing in enumerate(self.practice_cells):
                if existing == piece:
                    self.practice_cells[idx] = EMPTY
        self.practice_cells[sq] = piece
        self._refresh()

    def _practice_click(self, sq):
        if not self.practice_mode or sq is None:
            return
        self._practice_place(sq, self.practice_brush)

    def _practice_drop(self, origin, target):
        if not self.practice_mode or origin is None:
            return
        piece = self.practice_cells[origin]
        if not piece:
            return
        if target is None:
            self.practice_cells[origin] = EMPTY
        elif target != origin:
            self.practice_cells[origin] = EMPTY
            self.practice_cells[target] = piece
        self._refresh()

    def _practice_delete(self, sq):
        if not self.practice_mode or sq is None:
            return
        if self.practice_cells[sq]:
            self.practice_cells[sq] = EMPTY
            self._refresh()

    def start_practice_game(self):
        if not self.practice_mode:
            return
        ply = CANNON_UNLOCK_PLY if self.practice_cannon_open.get() else 0
        board, error = validate_custom_position(
            self.practice_cells, self.practice_turn, balanced=self.balanced, ply=ply
        )
        if board is None:
            self._refresh()
            return
        self.practice_mode = False
        self.board = board
        self.record = []
        self._clear_plan()
        self.view.clear_annotations()
        self.bot_note = ""
        self._update_position()

    def _on_log_scroll(self, first, last):
        self.log_scroll.set(first, last)
        if float(first) <= 0 and float(last) >= 1:
            self.log_scroll.grid_remove()
        else:
            self.log_scroll.grid()

    def _options(self, parent, title, entries, setter, *, margin=0, columns=None):
        self._label(parent, title, 9, bold=True).pack(anchor="w", pady=(margin, 3))
        row = tk.Frame(parent, bg=PAPER)
        row.pack(fill="x")
        buttons = {}
        columns = len(entries) if columns is None else columns
        for column in range(columns):
            row.grid_columnconfigure(column, weight=1, uniform="option")
        for index, (text, value) in enumerate(entries):
            grid_row, column = divmod(index, columns)
            button = self._button(row, text, lambda setting=value: setter(setting), compact=True)
            button.grid(row=grid_row, column=column, sticky="ew",
                        padx=(4 if column else 0, 0), pady=(4 if grid_row else 0, 0))
            buttons[value] = button
        return buttons

    @staticmethod
    def _set_active(buttons, value):
        for option, button in buttons.items():
            selected = option == value
            normal, foreground, hover = (GOLD, NAV, "#f5d89f") if selected else (SOFT, INK, HOVER)
            button.normal_color = normal
            button.configure(bg=normal, fg=foreground, activebackground=hover, activeforeground=foreground)

    def set_ruleset(self, balanced):
        if balanced == self.balanced:
            return
        if self.practice_mode:
            self.balanced = balanced
            self._refresh()
            return
        self._cancel_bot()
        self.saved_games[self.balanced] = self.board, self.record, self.bot_note
        self.balanced = balanced
        saved = self.saved_games.pop(balanced, None)
        if saved is None:
            self.new_game()
            return
        self.board, self.record, self.bot_note = saved
        self._clear_plan()
        self.view.clear_annotations()
        self._update_position()

    def set_mode(self, enabled):
        if enabled == self.vs_bot:
            return
        self._cancel_bot()
        self.vs_bot = enabled
        self._clear_plan()
        self._refresh()
        if not self.practice_mode:
            self._maybe_start_bot()

    def set_human(self, side):
        if side == self.human:
            return
        self._cancel_bot()
        self.human = side
        self._clear_plan()
        self._refresh()
        if not self.practice_mode:
            self._maybe_start_bot()

    def set_time(self, seconds):
        if seconds == self.think_time:
            return
        self._cancel_bot()
        self.think_time = seconds
        expert = seconds == EXPERT_SECONDS
        if self.engine.expert != expert:
            self.engine = Search(expert=expert)
        self._refresh()
        if not self.practice_mode:
            self._maybe_start_bot()

    def _board_flipped(self):
        return self.vs_bot and self.human == CHESS

    def set_chess_color(self, color):
        if color == self.chess_color or not valid_piece_colors(color, self.xiangqi_color):
            return
        self.chess_color = color
        self._refresh()

    def set_xiangqi_color(self, color):
        if color == self.xiangqi_color or not valid_piece_colors(self.chess_color, color):
            return
        self.xiangqi_color = color
        self._refresh()

    def new_game(self):
        self._cancel_bot()
        self.practice_mode = False
        self.board = Board(balanced=self.balanced)
        self.record = []
        self._clear_plan()
        self.view.clear_annotations()
        self.bot_note = ""
        self._update_position()

    def _update_position(self, apply_premove=False):
        self.legal = self.board.legal_moves()
        self.outcome = self.board.outcome(self.legal)
        if self.outcome is not None:
            self.premoves.clear()
        elif apply_premove and self.premoves:
            move = self.premoves.take(self.board, self.legal)
            if move is not None:
                self._play(move)
                return
            self.premove_note = "PreMove đã hủy vì nước đi không còn hợp lệ."
        self.check = self.board.in_check() if self.outcome is None else (
            self.outcome.reason == CHECKMATE
        )
        self._refresh()
        self._maybe_start_bot()

    def _refresh(self):
        self._set_active(self.ruleset_buttons, self.balanced)
        self._set_active(self.mode_buttons, self.vs_bot)
        self._set_active(self.chess_color_buttons, self.chess_color)
        self._set_active(self.xiangqi_color_buttons, self.xiangqi_color)
        for button, disabled in (
            (self.chess_color_buttons["black"], self.xiangqi_color == "black"),
            (self.xiangqi_color_buttons["black"], self.chess_color == "black"),
        ):
            button.configure(state="disabled" if disabled else "normal")
            if disabled:
                button.configure(cursor="", bg=button.normal_color)
        self._set_active(self.side_buttons, self.human)
        self._set_active(self.time_buttons, self.think_time)
        if self.vs_bot:
            self.bot_panel.pack(fill="x")
        else:
            self.bot_panel.pack_forget()
        pb_normal, pb_fg, pb_hover = (GOLD, NAV, "#f5d89f") if self.practice_mode else (NAV_CONTROL, NAV_TEXT, HOVER)
        self.practice_button.normal_color = pb_normal
        self.practice_button.configure(bg=pb_normal, fg=pb_fg, activebackground=pb_hover, activeforeground=pb_fg)

        flipped = self._board_flipped()
        if self.practice_mode:
            self.history_card.pack_forget()
            self.practice_panel.pack(fill="both", expand=True)
            self._set_active(self.practice_turn_buttons, self.practice_turn)
            er_sel = self.practice_brush == EMPTY
            er_normal, er_fg, er_hover = (GOLD, NAV, "#f5d89f") if er_sel else (SOFT, INK, HOVER)
            self.eraser_button.normal_color = er_normal
            self.eraser_button.configure(bg=er_normal, fg=er_fg, activebackground=er_hover, activeforeground=er_fg)
            self._redraw_palette()
            ply = CANNON_UNLOCK_PLY if self.practice_cannon_open.get() else 0
            valid_board, err = validate_custom_position(
                self.practice_cells, self.practice_turn, balanced=self.balanced, ply=ply
            )
            if err is not None:
                self.practice_status.configure(text=err, fg=EAST)
                self.practice_start_button.configure(state="disabled", cursor="", bg=self.practice_start_button.normal_color)
            else:
                self.practice_status.configure(text="Thế cờ hợp lệ · Bấm để bắt đầu chơi.", fg=WEST)
                self.practice_start_button.configure(state="normal")
            chess_mark = "♔" if self.chess_color == "white" else "♚"
            xiangqi_mark = "將" if self.xiangqi_color == "black" else "帥"
            for seat_side, (bar, mark_label, name, status, accent) in self.seats.items():
                seat_row = (2 if seat_side == CHESS else 0) if flipped else (0 if seat_side == CHESS else 2)
                bar.grid(row=seat_row, column=0, sticky="ew", padx=10, pady=(6, 0))
                mark_label.configure(text=chess_mark if seat_side == CHESS else xiangqi_mark)
                text = SIDE_NAMES[seat_side]
                if self.vs_bot:
                    text += " · " + ("Bạn" if seat_side == self.human else "Máy")
                name.configure(text=text)
                active = seat_side == self.practice_turn
                status.configure(text="Đi trước" if active else "")
                accent.configure(bg=status.cget("fg") if active else BORDER)
            side_color, tint = (WEST, WEST_TINT) if self.practice_turn == CHESS else (EAST, EAST_TINT)
            self.turn_icon.itemconfigure(self.icon_tile, fill=tint)
            self.turn_icon.itemconfigure(
                self.icon_piece,
                image=self.view.western_image(WK, 36, self.chess_color),
                state="normal" if self.practice_turn == CHESS else "hidden",
            )
            self.turn_icon.itemconfigure(
                self.icon_mark,
                text="" if self.practice_turn == CHESS else xiangqi_mark,
                fill=side_color, font=(self.chinese_font, -25, "bold"),
            )
            self.turn_context.configure(text="PHÒNG TẬP")
            self.turn_label.configure(text="Xếp thế cờ", fg=GOLD)
            brush_name = "Xóa quân" if self.practice_brush == EMPTY else f"{PIECE_NAMES[self.practice_brush]} ({SIDE_NAMES[SIDE[self.practice_brush]]})"
            self.status_label.configure(text=f"Đang chọn: {brush_name}", fg=MUTED)
            preview_board = Board(balanced=self.balanced)
            occupied = frozenset(sq for sq in SQUARES if self.practice_cells[sq])
            self.view.show_position(
                preview_board, None, frozenset(), None, None, occupied,
                projected=self.practice_cells, premoves=(), show_targets=False,
                flipped=flipped, chess_color=self.chess_color, xiangqi_color=self.xiangqi_color,
                editing=True,
            )
            return
        self.practice_panel.pack_forget()
        self.history_card.pack(fill="both", expand=True)

        side = self.board.turn
        opponent = self._opponent_side()
        if self.threat_source is not None:
            inspected = self.board.cells[self.threat_source]
            if not inspected or SIDE[inspected] != opponent:
                self.threat_source = None
        threat_targets = self.board.threat_targets(self.threat_source) if self.threat_source is not None else frozenset()
        can_play = self.outcome is None and (not self.vs_bot or side == self.human)
        self.planning = (
            self.outcome is None and self.vs_bot and side != self.human
            and self.job is not None and self.enable_premoves.get()
        )
        projected, rights = self.premoves.project(self.board) if self.planning else (None, self.board.rights)
        self.input_cells = self.board.cells if projected is None else projected
        self.input_side = side if can_play else None
        self.input_moves = ()
        if can_play:
            candidates = frozenset(move.src for move in self.legal)
            self.input_moves = tuple(move for move in self.legal if move.src == self.selection)
        elif self.planning and len(self.premoves) < MAX_PREMOVES:
            self.input_side = self.human
            candidates = frozenset(sq for sq, piece in enumerate(self.input_cells) if SIDE[piece] == self.human)
            if self.selection in candidates:
                self.input_moves = possible_moves(
                    self.input_cells, rights, self.selection, balanced=self.board.balanced
                )
        else:
            candidates = frozenset()
        targets = frozenset(move.dst for move in self.input_moves)
        chess_mark = "♔" if self.chess_color == "white" else "♚"
        xiangqi_mark = "將" if self.xiangqi_color == "black" else "帥"
        for seat_side, (bar, mark_label, name, status, accent) in self.seats.items():
            seat_row = (2 if seat_side == CHESS else 0) if flipped else (0 if seat_side == CHESS else 2)
            bar.grid(row=seat_row, column=0, sticky="ew", padx=10, pady=(6, 0))
            mark_label.configure(text=chess_mark if seat_side == CHESS else xiangqi_mark)
            text = SIDE_NAMES[seat_side]
            if self.vs_bot:
                role = "Bạn" if seat_side == self.human else "Máy"
                text += f" · {role}"
            name.configure(text=text)
            active = self.outcome is None and seat_side == side
            status.configure(text=("Bị chiếu" if self.check else "Đang đi") if active else "")
            accent.configure(bg=status.cget("fg") if active else BORDER)
        active_side = side
        color = EAST if self.check else MUTED
        if self.outcome is not None:
            active_side = self.outcome.winner
            context = "KẾT QUẢ"
            title = "Hòa cờ" if active_side is None else f"{SIDE_NAMES[active_side]} thắng"
            detail = REASONS[self.outcome.reason]
            color = MUTED
        else:
            title = SIDE_NAMES[side]
            context = "LƯỢT ĐI"
            if self.vs_bot:
                context = "LƯỢT CỦA BẠN" if can_play else "LƯỢT CỦA BOT"
            if self.job is not None:
                detail = self._thinking_message()
            elif self.threat_source is not None and self.selection is None:
                piece = self.board.cells[self.threat_source]
                hits = sum(1 for sq in threat_targets if self.board.cells[sq])
                hit_note = f" ({hits} quân bị đe dọa)" if hits else ""
                detail = f"Đe dọa: {PIECE_NAMES[piece]} · {coordinates(self.threat_source)} · {len(threat_targets)} ô{hit_note}"
            elif self.premove_note and self.selection is None:
                detail = self.premove_note
            elif self.selection is not None:
                piece = self.board.cells[self.selection]
                destination = f"{len(targets)} điểm đến" if targets else "Hết nước đi"
                detail = f"{PIECE_NAMES[piece]} · {coordinates(self.selection)} · {destination}"
            elif self.bot_note and self.vs_bot:
                detail = self.bot_note
            else:
                detail = "Chọn một quân để đi"
            if self.check:
                detail = "Đang bị chiếu" if self.selection is None and self.job is None else f"Đang bị chiếu · {detail}"

        if active_side == CHESS:
            mark, mark_font, side_color, tint = "", self.chess_font, WEST, WEST_TINT
        elif active_side == XIANGQI:
            mark, mark_font, side_color, tint = xiangqi_mark, self.chinese_font, EAST, EAST_TINT
        else:
            mark, mark_font, side_color, tint = "=", self.ui_font, INK, SOFT
        self.turn_icon.itemconfigure(self.icon_tile, fill=tint)
        self.turn_icon.itemconfigure(
            self.icon_piece,
            image=self.view.western_image(WK, 36, self.chess_color),
            state="normal" if active_side == CHESS else "hidden",
        )
        self.turn_icon.itemconfigure(self.icon_mark, text=mark, fill=side_color, font=(mark_font, -25, "bold"))
        self.turn_context.configure(text=context)
        self.turn_label.configure(text=title, fg=side_color)
        self.status_label.configure(text=detail, fg=color)
        self.undo_button.configure(state="normal" if self._undo_count() else "disabled")
        self._refresh_history()
        last = self.record[-1][0] if self.record and self.show_last_move.get() else None
        self.view.show_position(
            self.board, self.selection, targets, last,
            self.board.kings[side] if self.check else None, candidates,
            projected=projected, premoves=self.premoves.moves, show_targets=self.show_legal_moves.get(),
            flipped=flipped, chess_color=self.chess_color, xiangqi_color=self.xiangqi_color,
            threat_source=self.threat_source, threat_targets=threat_targets,
        )

    def _thinking_message(self):
        if not self.planning:
            return "Bot đang suy nghĩ…"
        count = len(self.premoves)
        if self.selection is not None and self.input_moves:
            name = PIECE_NAMES[self.input_cells[self.selection]]
            return f"Đặt trước {name} · {coordinates(self.selection)}"
        if count:
            return f"PreMove {count}/{MAX_PREMOVES} · Esc để hủy"
        return self.premove_note or "Bot đang suy nghĩ · Có thể đặt trước"

    def _refresh_history(self):
        moves = tuple((move, undo.piece, bool(undo.capture)) for move, undo in self.record)
        if moves == self.displayed_log:
            return
        self.displayed_log = moves
        self.log.delete(*self.log.get_children())
        self.log_count.configure(text=f"{len(moves)} nước" if moves else "")
        if not moves:
            self.empty_log.place(relx=.5, rely=.54, anchor="center")
            return
        self.empty_log.place_forget()
        for index, (move, piece, capture) in enumerate(moves, start=1):
            if move.rook_from >= 0:
                notation = "Nhập thành xa" if move.dst < move.src else "Nhập thành gần"
            else:
                arrow = "×" if capture else "→"
                notation = f"{coordinates(move.src)}  {arrow}  {coordinates(move.dst)}"
                if move.promotion:
                    notation += f" = {PIECE_NAMES[move.promotion]}"
            row = self.log.insert("", "end", values=(index, PIECE_NAMES[piece], notation),
                                  tags=(f"{SIDE[piece]}-{(index - 1) % 2}",))
        self.log.see(row)

    def _opponent_side(self):
        return 1 - self.human if self.vs_bot else 1 - self.board.turn

    def _inspect_threat(self, sq):
        piece = self.board.cells[sq]
        if piece and SIDE[piece] == self._opponent_side():
            self.threat_source = None if self.threat_source == sq else sq
            self._refresh()
            return True
        if self.threat_source is not None:
            self.threat_source = None
            self._refresh()
        return False

    def grab(self, sq):
        if self.input_side is not None and SIDE[self.input_cells[sq]] == self.input_side:
            self.threat_source = None
            self.selection = sq
            self._refresh()

    def pick(self, sq, dragged=False):
        if self.threat_source is not None:
            self.threat_source = None
            if self.input_side is None:
                self._refresh()
                return
        if self.input_side is None:
            return
        own_piece = sq is not None and SIDE[self.input_cells[sq]] == self.input_side
        choices = [move for move in self.input_moves if move.dst == sq]
        if choices and (dragged or not self.planning or not own_piece):
            commit = self._queue_move if self.planning else self._play
            if len(choices) > 1:
                self._choose_promotion(choices, commit)
            else:
                commit(choices[0])
            return
        self.selection = sq if not dragged and own_piece and sq != self.selection else None
        self._refresh()

    def _queue_move(self, move):
        if self.planning and self.premoves.add(self.input_cells[move.src], move):
            self.selection = None
            self.premove_note = ""
            self._refresh()

    def _clear_plan(self):
        self.premoves.clear()
        self.premove_note = ""
        self.selection = None
        self.threat_source = None
        if self.promotion_window is not None and self.promotion_window.winfo_exists():
            self.promotion_window.destroy()
        self.view.cancel_gestures()

    def _cancel_premove_at(self, sq):
        if not any(sq in (move.src, move.dst) for move in self.premoves.moves):
            return False
        self._clear_plan()
        self.premove_note = "Đã hủy PreMove."
        self._refresh()
        return True

    def _escape_board(self):
        had_plan = bool(self.premoves)
        self._clear_plan()
        if had_plan:
            self.premove_note = "Đã hủy PreMove."
        self.view.clear_annotations()
        self._refresh()

    def _play(self, move, apply_premove=False):
        undo = self.board.push_legal(move)
        if undo is None:
            raise ValueError("GameApp received an illegal move")
        self.record.append((move, undo))
        self.selection = None
        self.premove_note = ""
        self._update_position(apply_premove)

    def _undo_count(self):
        if not self.record:
            return 0
        if not self.vs_bot or SIDE[self.record[-1][1].piece] == self.human:
            return 1
        return 2 if len(self.record) >= 2 else 0

    def undo(self):
        if self.practice_mode:
            return
        count = self._undo_count()
        if not count:
            return
        self._cancel_bot()
        for _ in range(count):
            move, before = self.record.pop()
            self.board.pop(move, before)
        self._clear_plan()
        self.view.clear_annotations()
        self.bot_note = ""
        self._update_position()

    def _maybe_start_bot(self):
        if not self.vs_bot or self.board.turn == self.human or self.outcome is not None or self.job is not None:
            return
        cancel, result = Event(), Queue(maxsize=1)
        self.job = (cancel, result)
        position, engine, seconds = self.board.copy(), self.engine, self.think_time

        def think():
            try:
                result.put(engine.analyze(position, seconds, cancel))
            except Exception:
                logging.exception("Bot analysis failed")
                result.put(None)

        self._refresh()
        Thread(target=think, daemon=True, name="co-xam-bot").start()
        self.root.after(35, self._poll_bot, result)

    def _poll_bot(self, queue):
        if self.job is None or self.job[1] is not queue:
            return
        if self.promotion_window is not None and self.promotion_window.winfo_exists():
            self.root.after(35, self._poll_bot, queue)
            return
        try:
            result = queue.get_nowait()
        except Empty:
            self.root.after(35, self._poll_bot, queue)
            return
        self.job = None
        if result is not None and result.move in self.legal:
            self.bot_note = f"Bot · sâu {result.depth} · {result.nodes:,} nút".replace(",", ".")
            self._play(result.move, apply_premove=True)
        else:
            self.bot_note = "Bot đã dùng một nước dự phòng"
            self._play(self.legal[0], apply_premove=True)

    def _cancel_bot(self):
        if self.job is not None:
            self.job[0].set()
            self.job = None
            self.engine = Search(expert=self.think_time == EXPERT_SECONDS)

    def _dialog(self, title):
        dialog = tk.Toplevel(self.root, bg=PAPER)
        dialog.withdraw()
        dialog.title(title)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        return dialog

    def _show_dialog(self, dialog, modal=False):
        dialog.update_idletasks()
        width, height = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        x = min(max(0, x), max(0, self.root.winfo_screenwidth() - width - 18))
        y = min(max(0, y), max(0, self.root.winfo_screenheight() - height - 55))
        dialog.geometry(f"+{x}+{y}")
        dialog.deiconify()
        dialog.focus_set()
        if modal:
            dialog.grab_set()

    def _choose_promotion(self, moves, commit):
        dialog = self._dialog("Phong cấp")
        self.promotion_window = dialog
        tk.Frame(dialog, bg=GOLD, height=3).pack(fill="x")
        content = tk.Frame(dialog, bg=PAPER, padx=20, pady=17)
        content.pack(fill="both", expand=True)
        self._label(content, "Chọn quân phong cấp", 17, bold=True, heading=True).pack(anchor="w")
        row = tk.Frame(content, bg=PAPER)
        row.pack(fill="x", pady=(13, 12))

        def promote(move):
            dialog.destroy()
            commit(move)

        for index, move in enumerate(moves):
            piece = move.promotion
            button = self._button(row, PIECE_NAMES[piece],
                                  lambda choice=move: promote(choice))
            button.configure(image=self.view.western_image(piece, 44, self.chess_color), compound="top", pady=8)
            row.grid_columnconfigure(index, weight=1, uniform="promotion")
            button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 5, 0))
        self._button(content, "Hủy", dialog.destroy).pack(anchor="e")
        self._show_dialog(dialog, modal=True)

    def _board_options_changed(self):
        if not self.enable_premoves.get() and (self.planning or self.premoves):
            self._clear_plan()
        self._refresh()

    def show_options(self):
        if self.options_window is not None and self.options_window.winfo_exists():
            self.options_window.lift()
            self.options_window.focus_set()
            return
        dialog = self._dialog("Tùy chọn bàn cờ")
        self.options_window = dialog
        body = tk.Frame(dialog, bg=PAPER, padx=20, pady=15)
        body.pack(fill="both", expand=True)
        self._label(body, "Tùy chọn bàn cờ", 17, bold=True, heading=True).pack(anchor="w", pady=(0, 8))
        for title, setting in (
            ("Cho phép PreMove khi đấu máy", self.enable_premoves),
            ("Đánh dấu nước vừa đi", self.show_last_move),
            ("Hiện các điểm đến khi chọn quân", self.show_legal_moves),
        ):
            tk.Checkbutton(
                body, text=title, variable=setting, command=self._board_options_changed,
                bg=PAPER, activebackground=PAPER, fg=INK, selectcolor=SOFT,
                font=(self.ui_font, 10), anchor="w",
            ).pack(fill="x", pady=2)
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=9)
        self._label(body, "Nhấp hoặc kéo thả để đi quân. Chuột phải vào quân đối thủ để xem ô bị đe dọa. "
                    "Chuột phải ô trống để tô điểm, giữ chuột phải và kéo để vẽ mũi tên. Nhấp trái để xóa dấu.",
                    9, fg=MUTED, wrap=335).pack(anchor="w")
        self._button(body, "Đóng", dialog.destroy, kind="primary").pack(anchor="e", pady=(11, 0))
        self._show_dialog(dialog)

    def show_rules(self):
        if self.rules_window is not None and self.rules_window.winfo_exists():
            self.rules_window.lift()
            self.rules_window.focus_set()
            return
        dialog = self._dialog(f"Luật chơi · {GAME_NAME}")
        self.rules_window = dialog
        banner = tk.Frame(dialog, bg=NAV, padx=19, pady=13)
        banner.pack(fill="x")
        self._label(banner, "Luật chơi", 19, fg=NAV_TEXT, bg=NAV, bold=True, heading=True).pack(anchor="w")
        body = tk.Frame(dialog, bg=PAPER)
        body.pack(fill="both", expand=True, padx=16, pady=(12, 8))
        height = min(430, max(235, self.root.winfo_screenheight() - 235))
        pane = tk.Canvas(body, background=PAPER, width=490, height=height, highlightthickness=0)
        scroll = ttk.Scrollbar(body, orient="vertical", command=pane.yview, style="Paper.Vertical.TScrollbar")
        scroll.pack(side="right", fill="y")
        pane.pack(side="left", fill="both", expand=True)
        pane.configure(yscrollcommand=scroll.set)
        sections = tk.Frame(pane, bg=PAPER, padx=4)
        pane.create_window(0, 0, window=sections, anchor="nw", width=486)
        sections.bind("<Configure>", lambda _: pane.configure(scrollregion=pane.bbox("all")))
        dialog.bind("<MouseWheel>", lambda event: pane.yview_scroll(-int(event.delta / 120), "units"))
        for title, rule in RULES:
            section = tk.Frame(sections, bg=PAPER)
            section.pack(fill="x", pady=(2, 10))
            self._label(section, title, 11, bold=True).pack(anchor="w", pady=(0, 2))
            self._label(section, rule, 10, fg=MUTED, wrap=468).pack(anchor="w", pady=(0, 6))
            tk.Frame(section, bg=BORDER, height=1).pack(fill="x")
        self._button(dialog, "Đóng", dialog.destroy, kind="primary").pack(anchor="e", padx=17, pady=(0, 14))
        self._show_dialog(dialog)

    def close(self):
        self._cancel_bot()
        self.root.destroy()


def run():
    root = tk.Tk()
    GameApp(root)
    root.mainloop()
