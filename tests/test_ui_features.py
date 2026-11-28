from random import Random
import tkinter as tk
import unittest

from co_xam.board import (
    CHESS, XIANGQI, SIDE, SQUARES, WESTERN_PALACE,
    WK, WP, XC, XK, XP, Board, square,
)
from co_xam.board_view import BoardView, valid_piece_colors
from co_xam.ui import GameApp


class PieceColorRules(unittest.TestCase):
    def test_valid_piece_colors_blocks_both_black(self):
        self.assertTrue(valid_piece_colors("white", "red"))
        self.assertTrue(valid_piece_colors("black", "red"))
        self.assertTrue(valid_piece_colors("white", "black"))
        self.assertFalse(valid_piece_colors("black", "black"))
        self.assertFalse(valid_piece_colors("red", "red"))
        self.assertFalse(valid_piece_colors("white", "white"))

    def test_threat_targets_matches_is_attacked_across_random_games(self):
        rng = Random(2026)
        for balanced in (False, True):
            board = Board(balanced=balanced)
            for _ in range(30):
                legal = board.legal_moves()
                if board.outcome(legal) is not None:
                    break
                for side in (CHESS, XIANGQI):
                    union = set()
                    for src in board.positions[side]:
                        union.update(board.threat_targets(src))
                    expected = {
                        sq for sq in SQUARES
                        if (not board.cells[sq] or SIDE[board.cells[sq]] != side)
                        and board.is_attacked(sq, side)
                    }
                    self.assertEqual(union, expected)
                board.push_legal(rng.choice(legal))

    def test_threat_targets_handles_pawn_cannon_and_balanced_king(self):
        pawn_sq = square(2, 4)
        board = Board({square(0, 0): WK, square(8, 4): XK, pawn_sq: WP}, turn=XIANGQI, ply=6)
        self.assertEqual(board.threat_targets(pawn_sq), frozenset({square(3, 3), square(3, 5)}))
        river_pawn = square(3, 4)
        board_river = Board({square(0, 0): WK, square(8, 4): XK, river_pawn: WP}, turn=XIANGQI, ply=6)
        self.assertEqual(board_river.threat_targets(river_pawn), frozenset())

        cannon = square(6, 4)
        early = Board({square(0, 0): WK, square(8, 4): XK, cannon: XC, square(4, 4): WP}, turn=CHESS, ply=3)
        unlocked = Board({square(0, 0): WK, square(8, 4): XK, cannon: XC, square(4, 4): WP}, turn=CHESS, ply=5)
        self.assertNotIn(square(3, 3), early.threat_targets(cannon))
        self.assertIn(square(3, 3), unlocked.threat_targets(cannon))
        self.assertIn(square(3, 4), unlocked.threat_targets(cannon))

        balanced_king = Board({square(2, 5): WK, square(8, 4): XK}, balanced=True, turn=XIANGQI, ply=6)
        self.assertTrue(balanced_king.threat_targets(square(2, 5)) <= WESTERN_PALACE)


class BoardRotationAndUiBehavior(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.root.withdraw()

    def tearDown(self):
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def test_board_view_point_and_hit_test_round_trip_both_orientations(self):
        view = BoardView(self.root, lambda *_: None, lambda *_: None, lambda *_: False, "Arial", "Arial")
        view.winfo_width = lambda: 620
        view.winfo_height = lambda: 680
        board = Board(balanced=True)

        for flipped, chess_color, xiangqi_color in (
            (False, "white", "red"),
            (True, "white", "red"),
            (True, "black", "red"),
        ):
            view.show_position(
                board, None, frozenset(), None, None, frozenset(),
                flipped=flipped,
                chess_color=chess_color,
                xiangqi_color=xiangqi_color,
            )
            for sq in SQUARES:
                x, y = view.point(sq)
                self.assertEqual(view._at(x, y), sq, f"Mismatch at sq={sq}, flipped={flipped}, color={chess_color}")

            chess_back_y = view.point(square(0, 4))[1]
            xiangqi_back_y = view.point(square(8, 4))[1]
            queen_x = view.point(square(0, 3))[0]
            king_x = view.point(square(0, 4))[0]
            if flipped:
                self.assertGreater(chess_back_y, xiangqi_back_y)
                if chess_color == "white":
                    # White Chess at bottom: Queen on left (d), King on right (e)
                    self.assertLess(queen_x, king_x)
                    self.assertLess(view.point(square(0, 0))[0], view.point(square(0, 7))[0])
                else:
                    # Black Chess at bottom: King on left (e), Queen on right (d)
                    self.assertLess(king_x, queen_x)
                    self.assertLess(view.point(square(0, 7))[0], view.point(square(0, 0))[0])
            else:
                self.assertLess(chess_back_y, xiangqi_back_y)
                self.assertLess(queen_x, king_x)
                self.assertLess(view.point(square(0, 0))[0], view.point(square(0, 7))[0])

    def test_app_rotates_board_for_player_side_and_enforces_color_constraint_midgame(self):
        app = GameApp(self.root)
        try:
            # Default 2-player: Xiangqi at bottom
            self.assertFalse(app._board_flipped())
            self.assertEqual(int(app.seats[CHESS][0].grid_info()["row"]), 0)
            self.assertEqual(int(app.seats[XIANGQI][0].grid_info()["row"]), 2)

            # Play a move first to verify changing colors mid-match preserves board state
            first_move = app.legal[0]
            app._play(first_move)
            key_after_move = app.board.key

            # Switch to vs Bot as Chess (default human=CHESS) -> board flips so Chess is at bottom
            app.set_mode(True)
            app._cancel_bot()
            self.assertTrue(app._board_flipped())
            self.assertEqual(int(app.seats[CHESS][0].grid_info()["row"]), 2)
            self.assertEqual(int(app.seats[XIANGQI][0].grid_info()["row"]), 0)
            self.assertTrue(app.view.flipped)

            # Switch human to Xiangqi -> board un-flips so Xiangqi is at bottom
            app.set_human(XIANGQI)
            app._cancel_bot()
            self.assertFalse(app._board_flipped())
            self.assertEqual(int(app.seats[CHESS][0].grid_info()["row"]), 0)
            self.assertEqual(int(app.seats[XIANGQI][0].grid_info()["row"]), 2)
            self.assertFalse(app.view.flipped)

            # Change Chess to black mid-game -> Xiangqi black button disabled and rejected
            app.set_chess_color("black")
            self.assertEqual(app.chess_color, "black")
            self.assertEqual(app.xiangqi_color, "red")
            self.assertEqual(app.board.key, key_after_move)
            self.assertEqual(str(app.xiangqi_color_buttons["black"].cget("state")), "disabled")
            app.set_xiangqi_color("black")
            self.assertEqual(app.xiangqi_color, "red")

            # Change Chess back to white, then Xiangqi to black -> Chess black button disabled and rejected
            app.set_chess_color("white")
            self.assertEqual(str(app.xiangqi_color_buttons["black"].cget("state")), "normal")
            app.set_xiangqi_color("black")
            self.assertEqual(app.xiangqi_color, "black")
            self.assertEqual(str(app.chess_color_buttons["black"].cget("state")), "disabled")
            app.set_chess_color("black")
            self.assertEqual(app.chess_color, "white")
            self.assertEqual(app.board.key, key_after_move)

            # Right-clicking an opponent piece toggles its threat overlay; own piece clears it
            opp_knight = square(0, 1)  # Chess knight while human=XIANGQI
            own_pawn = square(5, 2)
            self.assertTrue(app._inspect_threat(opp_knight))
            self.assertEqual(app.threat_source, opp_knight)
            self.assertEqual(app.view.threat_targets, app.board.threat_targets(opp_knight))
            self.assertTrue(app._inspect_threat(opp_knight))
            self.assertIsNone(app.threat_source)
            self.assertTrue(app._inspect_threat(opp_knight))
            self.assertFalse(app._inspect_threat(own_pawn))
            self.assertIsNone(app.threat_source)
        finally:
            app._cancel_bot()


if __name__ == "__main__":
    unittest.main()
