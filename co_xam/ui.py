"""Tk interface and game controls for Akbar VS HanXin."""

import logging
from queue import Empty, Queue
from threading import Event, Thread
import tkinter as tk
from tkinter import font, ttk

from . import GAME_NAME
from .board import (
    CHESS, XIANGQI, SIDE, SIDE_NAMES, PIECE_NAMES,
    FACE_LOSS, CHECKMATE, STALEMATE, REPETITION, NO_PROGRESS,
    Board, coordinates,
)
from .board_view import BoardView, WEST_MARKS, STAGE, LEGAL, CAPTURE, LAST_MOVE
from .search import Search

APP_BG = "#f2eee5"
PAPER = "#fffcf5"
BORDER = "#d9d1c3"
INK = "#203344"
MUTED = "#546473"
NAV = "#162837"
NAV_CONTROL = "#284050"
NAV_TEXT = "#fff6e4"
GOLD = "#ebc783"
SOFT = "#f2eee5"
HOVER = "#e8dfcd"
WEST = "#24496a"
WEST_TINT = "#e3ebf1"
EAST = "#94362e"
EAST_TINT = "#f3e1da"

REASONS = {
    FACE_LOSS: "Lộ mặt Tướng",
    CHECKMATE: "Chiếu hết",
    STALEMATE: "Hết nước đi hợp lệ",
    REPETITION: "Thế cờ lặp lại 3 lần",
    NO_PROGRESS: "50 lượt mỗi bên không bắt quân hoặc đi Tốt",
}

RULES = (
    ("Bắt đầu", "Cờ tướng đi trước. Chọn quân rồi chọn một điểm được đánh dấu để đi."),
    ("Qua sông", "Một nước vượt sông dừng ở bờ đến. Ô cờ vua ứng với hai giao điểm "
     "cờ tướng kề nó. Đường kẻ ngoài cùng chỉ có một ô cờ vua tương ứng."),
    ("Hậu, Tượng và Tốt", "Hậu và Tượng cờ vua đi tối đa hai bước khi xuất phát "
     "trên phần cờ tướng. Khi qua sông, Tốt cờ vua chỉ tiến thẳng đến giao điểm trống. "
     "Tốt hai bên có thể đi hoặc ăn ngang sau khi qua sông. "
     "Tốt cờ vua phong cấp ở hàng cuối bên kia."),
    ("Mã và cung Tướng", "Mã hai bên bị chặn chân khi xuất phát trên phần cờ tướng. "
     "Trên phần cờ vua, Mã nhảy tự do. Tướng và Sĩ ở trong cung. Tượng cờ tướng không qua sông."),
    ("Pháo", "Pháo cần đúng một quân làm ngòi khi ăn quân. Trong ba lượt đầu "
     "của bên cờ tướng, ngòi phải là quân cờ tướng."),
    ("Nhập thành và lộ mặt Tướng", "Vua cờ vua được nhập thành theo luật cờ vua. "
     "Nếu Vua đi làm lộ mặt Tướng, bên cờ tướng thắng. Các nước khác làm hai quân lộ mặt bị cấm."),
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
        root.bind("<Escape>", lambda _: self.pick(None))
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
        stage.grid_rowconfigure(0, weight=1)
        self.view = BoardView(stage, self.pick, self.ui_font, self.chess_font, self.chinese_font)
        self.view.grid(row=0, column=0, sticky="nsew")
        self._build_legend(stage)

        panel = tk.Frame(body, bg=APP_BG, width=328)
        panel.grid(row=0, column=1, sticky="ns")
        panel.pack_propagate(False)
        self._build_controls(panel)

        self.vs_bot = False
        self.human = CHESS
        self.think_time = 3
        self.job = None
        self.rules_window = None
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
        style.configure("Paper.Vertical.TScrollbar", background="#d4cabc", troughcolor=PAPER,
                        borderwidth=0, relief="flat", arrowsize=11)

    def _label(self, parent, text, size=10, *, fg=INK, bg=PAPER, bold=False, heading=False, wrap=0):
        family = self.heading_font if heading else self.ui_font
        return tk.Label(parent, text=text, font=(family, size, "bold" if bold else "normal"),
                        fg=fg, bg=bg, anchor="w", justify="left", wraplength=wrap, padx=0, pady=0)

    def _button(self, parent, text, command, *, kind="plain", compact=False):
        normal, foreground, hover = {
            "primary": (GOLD, NAV, "#f5d89f"),
            "nav": (NAV_CONTROL, NAV_TEXT, "#38566b"),
            "plain": (SOFT, INK, HOVER),
        }[kind]
        button = tk.Button(
            parent, text=text, command=command, relief="flat", borderwidth=0,
            bg=normal, fg=foreground, activebackground=hover, activeforeground=foreground,
            disabledforeground="#706b62", font=(self.ui_font, 9 if compact else 10, "bold"),
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
        seal.create_line(27, 9, 20, 38, fill="#7e929e")
        seal.create_text(14, 23, text="♞", fill=NAV_TEXT, font=(self.chess_font, -19))
        seal.create_text(33, 23, text="帥", fill=GOLD, font=(self.chinese_font, -15, "bold"))
        title = tk.Frame(nav, bg=NAV)
        title.pack(side="left")
        self._label(title, GAME_NAME, 23, fg=NAV_TEXT, bg=NAV, bold=True, heading=True).pack(anchor="w")
        self._label(title, "Cờ vua × Cờ tướng", 9, fg="#c4cfd3", bg=NAV).pack(anchor="w")
        self.rules_button = self._button(nav, "Luật chơi", self.show_rules, kind="nav")
        self.rules_button.pack(side="right")
        self.new_button = self._button(nav, "Ván mới", self.new_game, kind="primary")
        self.new_button.pack(side="right", padx=(0, 8))
        tk.Frame(self.root, bg=GOLD, height=2).grid(row=0, column=0, sticky="sew")

    def _build_legend(self, stage):
        legend = tk.Frame(stage, bg=STAGE, pady=6)
        legend.grid(row=1, column=0)
        for name, color, shape in (
            ("Nước hợp lệ", LEGAL, "dot"),
            ("Ăn quân", CAPTURE, "ring"),
            ("Nước vừa đi", LAST_MOVE, "box"),
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
                marker.create_rectangle(3, 3, 13, 13, fill="#f6dba1", outline=color)
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
        self.mode_buttons = self._options(settings, "Chế độ chơi", (("Hai người", False), ("Đấu máy", True)), self.set_mode)
        self.bot_panel = tk.Frame(settings, bg=PAPER)
        self.side_buttons = self._options(
            self.bot_panel, "Bạn cầm", (("Cờ vua", CHESS), ("Cờ tướng", XIANGQI)), self.set_human, margin=7
        )
        self.time_buttons = self._options(
            self.bot_panel, "Thời gian bot", (("1 giây", 1), ("3 giây", 3), ("8 giây", 8)), self.set_time, margin=7
        )

        history = self._card(panel, padx=10)
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
            self.log.tag_configure(f"{side}-1", background="#f7f3e9", foreground=color)
        self.log_scroll = ttk.Scrollbar(scrollable, orient="vertical", command=self.log.yview,
                                        style="Paper.Vertical.TScrollbar")
        self.log_scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=self._on_log_scroll)
        self.empty_log = self._label(scrollable, "Chưa có nước đi", 9, fg=MUTED)

    def _on_log_scroll(self, first, last):
        self.log_scroll.set(first, last)
        if float(first) <= 0 and float(last) >= 1:
            self.log_scroll.grid_remove()
        else:
            self.log_scroll.grid()

    def _options(self, parent, title, entries, setter, *, margin=0):
        self._label(parent, title, 9, bold=True).pack(anchor="w", pady=(margin, 3))
        row = tk.Frame(parent, bg=PAPER)
        row.pack(fill="x")
        buttons = {}
        for index, (text, value) in enumerate(entries):
            row.grid_columnconfigure(index, weight=1, uniform="option")
            button = self._button(row, text, lambda setting=value: setter(setting), compact=True)
            button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 4, 0))
            buttons[value] = button
        return buttons

    @staticmethod
    def _set_active(buttons, value):
        for option, button in buttons.items():
            selected = option == value
            normal, foreground, hover = (NAV, NAV_TEXT, NAV_CONTROL) if selected else (SOFT, INK, HOVER)
            button.normal_color = normal
            button.configure(bg=normal, fg=foreground, activebackground=hover, activeforeground=foreground)

    def set_mode(self, enabled):
        if enabled == self.vs_bot:
            return
        self._cancel_bot()
        self.vs_bot = enabled
        self.selection = None
        self._refresh()
        self._maybe_start_bot()

    def set_human(self, side):
        if side == self.human:
            return
        self._cancel_bot()
        self.human = side
        self.selection = None
        self._refresh()
        self._maybe_start_bot()

    def set_time(self, seconds):
        if seconds == self.think_time:
            return
        self._cancel_bot()
        self.think_time = seconds
        self._refresh()
        self._maybe_start_bot()

    def new_game(self):
        self._cancel_bot()
        self.board = Board()
        self.record = []
        self.selection = None
        self.bot_note = ""
        self._update_position()

    def _update_position(self):
        self.legal = self.board.legal_moves()
        self.outcome = self.board.outcome(self.legal)
        self.check = self.board.in_check() if self.outcome is None else (
            self.outcome.reason == CHECKMATE
        )
        self._refresh()
        self._maybe_start_bot()

    def _refresh(self):
        self._set_active(self.mode_buttons, self.vs_bot)
        self._set_active(self.side_buttons, self.human)
        self._set_active(self.time_buttons, self.think_time)
        if self.vs_bot:
            self.bot_panel.pack(fill="x")
        else:
            self.bot_panel.pack_forget()

        side = self.board.turn
        can_play = self.outcome is None and (not self.vs_bot or side == self.human)
        targets = frozenset(move.dst for move in self.legal if move.src == self.selection)
        candidates = frozenset(move.src for move in self.legal) if can_play else frozenset()
        active_side = side
        color = CAPTURE if self.check else MUTED
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
                detail = "Bot đang suy nghĩ…"
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
            mark, mark_font, side_color, tint = "♚", self.chess_font, WEST, WEST_TINT
        elif active_side == XIANGQI:
            mark, mark_font, side_color, tint = "帥", self.chinese_font, EAST, EAST_TINT
        else:
            mark, mark_font, side_color, tint = "=", self.ui_font, INK, SOFT
        self.turn_icon.itemconfigure(self.icon_tile, fill=tint)
        self.turn_icon.itemconfigure(self.icon_mark, text=mark, fill=side_color, font=(mark_font, -25, "bold"))
        self.turn_context.configure(text=context)
        self.turn_label.configure(text=title, fg=side_color)
        self.status_label.configure(text=detail, fg=color)
        self.undo_button.configure(state="normal" if self._undo_count() else "disabled")
        self._refresh_history()
        last = self.record[-1][0] if self.record else None
        self.view.show_position(self.board, self.selection, targets, last,
                                self.board.kings[side] if self.check else None, candidates)

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

    def pick(self, sq):
        if self.outcome is not None or self.vs_bot and self.board.turn != self.human:
            return
        if sq is not None and self.selection is not None:
            candidates = [move for move in self.legal if move.src == self.selection and move.dst == sq]
            if len(candidates) > 1:
                self._choose_promotion(candidates)
                return
            if candidates:
                self._play(candidates[0])
                return
        self.selection = sq if (sq is not None and sq != self.selection
                                and SIDE[self.board.cells[sq]] == self.board.turn) else None
        self._refresh()

    def _play(self, move):
        undo = self.board.push_legal(move)
        if undo is None:
            raise ValueError("GameApp received an illegal move")
        self.record.append((move, undo))
        self.selection = None
        self._update_position()

    def _undo_count(self):
        if not self.record:
            return 0
        if not self.vs_bot or SIDE[self.record[-1][1].piece] == self.human:
            return 1
        return 2 if len(self.record) >= 2 else 0

    def undo(self):
        count = self._undo_count()
        if not count:
            return
        self._cancel_bot()
        for _ in range(count):
            move, before = self.record.pop()
            self.board.pop(move, before)
        self.selection = None
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
        try:
            result = queue.get_nowait()
        except Empty:
            self.root.after(35, self._poll_bot, queue)
            return
        self.job = None
        if result is not None and result.move in self.legal:
            self.bot_note = f"Bot · sâu {result.depth} · {result.nodes:,} nút".replace(",", ".")
            self._play(result.move)
        else:
            self.bot_note = "Bot đã dùng một nước dự phòng"
            self._play(self.legal[0])

    def _cancel_bot(self):
        if self.job is not None:
            self.job[0].set()
            self.job = None
            self.engine = Search()

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

    def _choose_promotion(self, moves):
        dialog = self._dialog("Phong cấp")
        tk.Frame(dialog, bg=GOLD, height=3).pack(fill="x")
        content = tk.Frame(dialog, bg=PAPER, padx=20, pady=17)
        content.pack(fill="both", expand=True)
        self._label(content, "Chọn quân phong cấp", 17, bold=True, heading=True).pack(anchor="w")
        row = tk.Frame(content, bg=PAPER)
        row.pack(fill="x", pady=(13, 12))

        def promote(move):
            dialog.destroy()
            self._play(move)

        for index, move in enumerate(moves):
            piece = move.promotion
            button = self._button(row, f"{WEST_MARKS[piece]}\n{PIECE_NAMES[piece]}",
                                  lambda choice=move: promote(choice))
            button.configure(font=(self.chess_font, 13, "bold"), width=6, pady=9)
            row.grid_columnconfigure(index, weight=1, uniform="promotion")
            button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 5, 0))
        self._button(content, "Hủy", dialog.destroy).pack(anchor="e")
        self._show_dialog(dialog, modal=True)

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
