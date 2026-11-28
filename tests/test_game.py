from random import Random
from threading import Event
import unittest

from co_xam.board import (
    CHESS, XIANGQI, CHECKMATE, REPETITION, STALEMATE, QUEENSIDE, KINGSIDE,
    WK, WQ, WR, WB, WN, WP, XK, XR, XC, XN, XE, XA, XP,
    Board, Move, Outcome, PROMOTIONS, square,
)
from co_xam.evaluation import BALANCED_MATERIAL, MATERIAL, evaluate
from co_xam.search import MATE, Search


def position(*pieces, turn=CHESS, ply=6, rights=0, balanced=False):
    setup = {square(0, 2 if balanced else 0): WK, square(8, 4): XK}
    for row, col, piece in pieces:
        setup[square(row, col)] = piece
    return Board(setup, turn=turn, rights=rights, ply=ply, balanced=balanced)


def moves_from(board, row, col):
    return {move.dst for move in board.legal_moves() if move.src == square(row, col)}


def signature(board):
    return (
        board.cells.copy(), [positions.copy() for positions in board.positions],
        board.kings.copy(), board.turn, board.rights, board.ply, board.quiet,
        board.key, board.history_key, board.counts.copy(), board.occupied,
    )


class BoardRules(unittest.TestCase):
    def test_crossing_stops_at_the_bank_and_edges_have_one_projection(self):
        board = position((2, 3, WR))
        destinations = moves_from(board, 2, 3)
        self.assertTrue({square(4, 3), square(4, 4)} <= destinations)
        self.assertNotIn(square(5, 3), destinations)
        blocked = position((2, 3, WR), (3, 3, WP))
        self.assertNotIn(square(4, 3), moves_from(blocked, 2, 3))
        board = position((5, 8, XR), turn=XIANGQI)
        destinations = moves_from(board, 5, 8)
        self.assertIn(square(3, 7), destinations)
        self.assertNotIn(square(3, 6), destinations)
        self.assertNotIn(square(2, 7), destinations)
        center = position((5, 5, XR), turn=XIANGQI)
        self.assertTrue({square(3, 4), square(3, 5)} <= moves_from(center, 5, 5))

    def test_adjacent_queen_rays_yield_one_move_to_a_shared_crossing_point(self):
        for src, dst in ((square(3, 5), square(4, 6)), (square(4, 5), square(3, 4))):
            with self.subTest(src=src, dst=dst):
                board = position((*divmod(src, 9), WQ), (*divmod(dst, 9), XC))
                move = Move(src, dst)
                self.assertEqual(board.legal_moves().count(move), 1)
                self.assertEqual(board.pseudo_moves(tactical_only=True).count(move), 1)

    def test_balanced_palace_limits_king_moves_and_attacks(self):
        origin = square(2, 3)
        outside = square(3, 3)
        inner = square(1, 2)
        pieces = {origin: WK, square(8, 5): XK, outside: XC}
        classic = Board(pieces, turn=CHESS, ply=6)
        balanced = Board(pieces, turn=CHESS, ply=6, balanced=True)

        capture = Move(origin, outside)
        self.assertIn(capture, classic.legal_moves())
        self.assertTrue(classic.is_attacked(outside, CHESS))
        self.assertNotIn(capture, balanced.pseudo_moves(tactical_only=True))
        self.assertIsNone(balanced.push_legal(capture))
        self.assertFalse(balanced.is_attacked(outside, CHESS))
        self.assertIn(Move(origin, inner), balanced.legal_moves())
        self.assertTrue(balanced.is_attacked(inner, CHESS))
        self.assertNotEqual(classic.key, balanced.key)

        snapshot = balanced.copy()
        self.assertTrue(snapshot.balanced)
        self.assertEqual(snapshot.key, balanced.key)
        self.assertEqual(set(snapshot.legal_moves()), set(balanced.legal_moves()))
        result = Search(table_bits=8).analyze(snapshot, 1, max_depth=2)
        self.assertIn(result.move, balanced.legal_moves())
        self.assertNotEqual(result.move, capture)

    def test_balanced_castling_stays_in_the_palace(self):
        pieces = {0: WR, 4: WK, 7: WR, square(8, 4): XK, square(5, 4): XP}
        rights = QUEENSIDE | KINGSIDE
        classic = Board(pieces, turn=CHESS, rights=rights, ply=6)
        balanced = Board(pieces, turn=CHESS, rights=rights, ply=6, balanced=True)
        long_castle = Move(4, 2, rook_from=0, rook_to=3)
        short_castle = Move(4, 6, rook_from=7, rook_to=5)
        self.assertIn(short_castle, classic.legal_moves())
        self.assertNotIn(short_castle, balanced.legal_moves())
        self.assertIsNone(balanced.push_legal(short_castle))
        self.assertEqual(balanced.rights, QUEENSIDE)
        self.assertIn(long_castle, balanced.legal_moves())
        before = signature(balanced)
        undo = balanced.push_legal(long_castle)
        self.assertEqual(balanced.kings[CHESS], 2)
        self.assertEqual(balanced.cells[3], WR)
        balanced.pop(long_castle, undo)
        self.assertEqual(signature(balanced), before)

    def test_balanced_elephant_crosses_both_ways_through_a_blocked_eye(self):
        bank = square(3, 2)
        piece = (5, 4, XE)
        blockers = ((4, 3, WP), (6, 5, XP), (3, 2, WN))
        classic = position(piece, *blockers, turn=XIANGQI)
        balanced = position(piece, *blockers, turn=XIANGQI, balanced=True)
        self.assertNotIn(bank, moves_from(classic, 5, 4))
        self.assertFalse(classic.is_attacked(bank, XIANGQI))
        self.assertTrue({bank, square(3, 1), square(7, 6)} <= moves_from(balanced, 5, 4))
        self.assertIn(Move(square(5, 4), bank), balanced.pseudo_moves(tactical_only=True))
        self.assertIn(bank, balanced.threat_targets(square(5, 4)))
        self.assertTrue(balanced.is_attacked(bank, XIANGQI))
        return_trip = position((2, 2, XE), (3, 3, WP), turn=XIANGQI, balanced=True)
        self.assertTrue({square(4, 4), square(4, 5)} <= moves_from(return_trip, 2, 2))

    def test_balanced_advisor_orthogonal_steps_and_palace_diagonals(self):
        inside = position((6, 3, XA), turn=XIANGQI, balanced=True)
        self.assertEqual(moves_from(inside, 6, 3), {
            square(5, 3), square(6, 2), square(6, 4), square(7, 3), square(7, 4),
        })
        outside = position((5, 3, XA), turn=XIANGQI, balanced=True)
        self.assertEqual(moves_from(outside, 5, 3), {
            square(4, 3), square(5, 2), square(5, 4), square(6, 3),
        })
        bank = position((4, 4, XA), turn=XIANGQI, balanced=True)
        self.assertTrue({square(3, 3), square(3, 4)} <= moves_from(bank, 4, 4))

    def test_balanced_western_rook_is_short_range_on_xiangqi_half(self):
        classic = position((5, 4, WR))
        balanced = position((5, 4, WR), balanced=True)
        two_steps = square(5, 6)
        three_steps = square(5, 7)
        self.assertIn(three_steps, moves_from(classic, 5, 4))
        self.assertTrue(classic.is_attacked(three_steps, CHESS))
        self.assertIn(two_steps, moves_from(balanced, 5, 4))
        self.assertNotIn(three_steps, moves_from(balanced, 5, 4))
        self.assertIn(two_steps, balanced.threat_targets(square(5, 4)))
        self.assertFalse(balanced.is_attacked(three_steps, CHESS))
        home = position((2, 0, WR), balanced=True)
        self.assertIn(square(2, 5), moves_from(home, 2, 0))

    def test_balanced_western_pawn_reaches_last_rank_and_moves_sideways(self):
        source = square(7, 2)
        last_rank = square(8, 2)
        victim = square(8, 3)
        board = position((7, 2, WP), (8, 3, XP), balanced=True)
        arrival = Move(source, last_rank)
        capture_arrival = Move(source, victim)
        self.assertEqual({move for move in board.legal_moves() if move.src == source},
                         {arrival, capture_arrival})
        self.assertIn(capture_arrival, board.pseudo_moves(tactical_only=True))
        self.assertNotIn(arrival, board.pseudo_moves(tactical_only=True))
        self.assertIsNone(board.push_legal(Move(source, last_rank, WQ)))
        undo = board.push_legal(arrival)
        self.assertEqual(board.cells[last_rank], WP)
        board.pop(arrival, undo)
        self.assertEqual(board.cells[source], WP)

        final = position((8, 2, WP), (8, 3, XP), (7, 2, XP), balanced=True)
        empty_neighbor = square(8, 1)
        self.assertEqual(moves_from(final, 8, 2), {empty_neighbor, victim})
        self.assertEqual({move.dst for move in final.pseudo_moves(tactical_only=True) if move.src == last_rank},
                         {victim})
        self.assertEqual(final.threat_targets(last_rank), {empty_neighbor, victim})
        self.assertTrue(final.is_attacked(victim, CHESS))

    def test_western_pawn_crosses_only_to_empty_points_beside_its_file(self):
        pawn = square(3, 4)  # e5
        left = square(4, 4)  # 5/5
        right = square(4, 5)  # 4/5
        cannon = square(4, 6)  # 3/5
        open_bank = position((3, 4, WP), (4, 6, XC))
        self.assertEqual(moves_from(open_bank, 3, 4), {left, right})

        blocked = position((3, 4, WP), (4, 5, WN), (4, 6, XC))
        self.assertEqual(moves_from(blocked, 3, 4), {left})
        self.assertFalse(any(move.src == pawn for move in blocked.pseudo_moves(tactical_only=True)))
        self.assertFalse(blocked.is_attacked(cannon, CHESS))

        occupied = position((3, 4, WP), (4, 4, XC), (4, 5, WN))
        self.assertEqual(moves_from(occupied, 3, 4), set())
        self.assertFalse(occupied.is_attacked(left, CHESS))

    def test_western_pawn_can_still_capture_diagonally_within_each_half(self):
        for row in (2, 4):
            with self.subTest(row=row):
                capture = square(row + 1, 5)
                board = position((row, 4, WP), (row + 1, 5, XC))
                self.assertIn(capture, moves_from(board, row, 4))
                self.assertTrue(board.is_attacked(capture, CHESS))

    def test_western_pawn_on_xiangqi_half_advances_and_captures_diagonally(self):
        board = position((5, 4, WP), (5, 3, XP), (6, 5, XC))
        self.assertEqual(moves_from(board, 5, 4), {square(6, 4), square(6, 5)})
        self.assertFalse(board.is_attacked(square(5, 3), CHESS))
        self.assertFalse(board.is_attacked(square(5, 5), CHESS))
        blocked = position((5, 4, WP), (6, 4, XP))
        self.assertFalse(moves_from(blocked, 5, 4))

    def test_general_diagonals_follow_only_the_lines_inside_the_palace(self):
        center = square(7, 4)
        from_center = Board({square(0, 0): WK, center: XK}, turn=XIANGQI)
        self.assertEqual(moves_from(from_center, 7, 4), {
            square(row, col) for row in range(6, 9) for col in range(3, 6)
        } - {center})
        self.assertTrue(from_center.is_attacked(square(6, 3), XIANGQI))

        corner = square(6, 3)
        from_corner = Board({square(0, 0): WK, corner: XK, center: WP}, turn=XIANGQI)
        self.assertIn(Move(corner, center), from_corner.pseudo_moves(tactical_only=True))
        self.assertIn(center, moves_from(from_corner, 6, 3))

        from_edge = Board({square(0, 0): WK, square(6, 4): XK}, turn=XIANGQI)
        self.assertEqual(moves_from(from_edge, 6, 4), {square(6, 3), square(6, 5), center})
        self.assertFalse(from_edge.is_attacked(square(7, 3), XIANGQI))

        checked_destination = Board({square(0, 0): WK, square(8, 3): XK, corner: WP}, turn=XIANGQI)
        self.assertNotIn(center, moves_from(checked_destination, 8, 3))

    def test_imported_pieces_use_the_current_half(self):
        queen = position((6, 1, WQ))
        self.assertIn(square(4, 1), moves_from(queen, 6, 1))
        self.assertNotIn(square(3, 0), moves_from(queen, 6, 1))
        bishop = position((7, 1, WB))
        self.assertIn(square(5, 3), moves_from(bishop, 7, 1))
        self.assertNotIn(square(4, 4), moves_from(bishop, 7, 1))
        horse = position((5, 2, WN), (5, 3, WP))
        self.assertNotIn(square(6, 4), moves_from(horse, 5, 2))
        freed = position((2, 2, XN), (2, 3, XP), turn=XIANGQI)
        self.assertIn(square(1, 4), moves_from(freed, 2, 2))
        self.assertIn(square(2, 3), moves_from(position((2, 2, XP), turn=XIANGQI), 2, 2))

    def test_horse_can_use_either_open_crossing_route(self):
        one_route = position((4, 4, XN), (4, 3, XP), turn=XIANGQI)
        none = position((4, 4, XN), (4, 3, XP), (3, 3, XP), turn=XIANGQI)
        self.assertIn(square(3, 2), moves_from(one_route, 4, 4))
        self.assertNotIn(square(3, 2), moves_from(none, 4, 4))

    def test_elephant_needs_a_clear_eye_and_stays_home(self):
        board = position((5, 2, XE), (6, 3, XP), turn=XIANGQI)
        self.assertEqual(moves_from(board, 5, 2), {square(7, 0)})
        guard = position((8, 3, XA), turn=XIANGQI)
        self.assertEqual(moves_from(guard, 8, 3), {square(7, 4)})

    def test_cannon_screen_restriction_and_number(self):
        target = square(3, 3)
        start = ((6, 4, XC), (3, 3, WP))
        early = position(*start, (4, 4, WP), turn=XIANGQI, ply=4)
        after = position(*start, (4, 4, WP), turn=XIANGQI, ply=5)
        friendly = position(*start, (4, 4, XP), turn=XIANGQI, ply=4)
        extra_screen = position(*start, (4, 4, XE), (5, 4, XP), turn=XIANGQI)
        for board, allowed in ((early, False), (after, True), (friendly, True), (extra_screen, False)):
            self.assertEqual(target in moves_from(board, 6, 4), allowed)
            self.assertEqual(board.is_attacked(target, XIANGQI), allowed)
        self.assertNotEqual(early.key, after.key)

    def test_promotion_and_castling_restore_every_state_field(self):
        promotion = position((7, 2, WP))
        choices = [m for m in promotion.legal_moves() if m.src == square(7, 2) and m.dst == square(8, 2)]
        self.assertEqual({choice.promotion for choice in choices}, set(PROMOTIONS))
        before = signature(promotion)
        for choice in choices:
            undo = promotion.push_legal(choice)
            self.assertEqual(promotion.cells[choice.dst], choice.promotion)
            promotion.pop(choice, undo)
            self.assertEqual(signature(promotion), before)

        board = Board({0: WR, 4: WK, 7: WR, square(8, 4): XK, square(5, 4): XP},
                      turn=CHESS, rights=QUEENSIDE | KINGSIDE, ply=6)
        castles = [move for move in board.legal_moves() if move.rook_from >= 0]
        self.assertEqual({move.dst for move in castles}, {2, 6})
        before = signature(board)
        for move in castles:
            undo = board.push_legal(move)
            self.assertEqual(board.cells[move.rook_to], WR)
            self.assertEqual(board.rights, 0)
            board.pop(move, undo)
            self.assertEqual(signature(board), before)

    def test_either_royal_is_forbidden_from_exposing_the_facing_line(self):
        cases = (
            (CHESS, square(0, 2), square(8, 4), Move(square(0, 2), square(0, 3))),
            (XIANGQI, square(0, 4), square(8, 3), Move(square(8, 3), square(7, 4))),
        )
        for turn, western, eastern, move in cases:
            with self.subTest(turn=turn):
                board = Board({western: WK, eastern: XK}, turn=turn, ply=6)
                before = signature(board)
                self.assertIn(move, board.pseudo_moves())
                self.assertNotIn(move, board.legal_moves())
                self.assertIsNone(board.push_legal(move))
                self.assertEqual(signature(board), before)
                self.assertIsNone(board.outcome())
                bot = Search(table_bits=8).analyze(board, 1, max_depth=2)
                self.assertIn(bot.move, board.legal_moves())

    def test_blocking_piece_may_only_leave_when_another_piece_keeps_the_line_closed(self):
        pieces = {square(0, 4): WK, square(8, 4): XK, square(3, 3): WQ, square(3, 0): XC}
        capture = Move(square(3, 3), square(3, 0))
        board = Board(pieces, turn=CHESS, ply=6)
        self.assertIn(capture, board.pseudo_moves(tactical_only=True))
        self.assertNotIn(capture, board.legal_moves())
        self.assertIsNone(board.outcome())

        covered = Board({**pieces, square(1, 4): WP}, turn=CHESS, ply=6)
        self.assertIn(capture, covered.legal_moves())

    def test_mate_and_stalemate(self):
        mate = position((0, 2, XR), (1, 0, XR), (1, 1, XP))
        self.assertEqual(mate.outcome(), Outcome(XIANGQI, CHECKMATE))
        self.assertEqual(Search(table_bits=8).analyze(mate).score, -MATE)
        stalemate = position((1, 1, XR), (2, 1, XP))
        self.assertEqual(stalemate.outcome(), Outcome(None, STALEMATE))
        self.assertIsNone(Search(table_bits=8).analyze(stalemate).move)

    def test_repetition_includes_reversible_sideways_pawn_moves(self):
        board = position((6, 1, WR), (2, 1, XP))
        cycle = ((6, 1, 6, 2), (2, 1, 2, 2), (6, 2, 6, 1), (2, 2, 2, 1))
        for src_r, src_c, dst_r, dst_c in cycle * 2:
            move = Move(square(src_r, src_c), square(dst_r, dst_c))
            self.assertIn(move, board.legal_moves())
            board.push_legal(move)
        self.assertEqual(board.outcome(), Outcome(None, REPETITION))

    def test_attack_tables_and_random_make_unmake(self):
        rng = Random(608)
        board = Board()
        start = signature(board)
        undo_stack = []
        for _ in range(100):
            legal = board.legal_moves()
            if board.outcome(legal) is not None:
                break
            self.assertEqual(len(legal), len(set(legal)))
            opponent = 1 - board.turn
            king = board.kings[opponent]
            board.kings[opponent] = -1
            attacks = {move.dst for move in board.pseudo_moves(tactical_only=True)}
            board.kings[opponent] = king
            for target in board.positions[opponent]:
                self.assertEqual(board.is_attacked(target, board.turn), target in attacks)
            move = rng.choice(legal)
            undo_stack.append((move, board.push_legal(move)))
            rebuilt = Board({sq: p for sq, p in enumerate(board.cells) if p},
                            turn=board.turn, rights=board.rights, ply=board.ply)
            self.assertEqual(rebuilt.key, board.key)
        for move, undo in reversed(undo_stack):
            board.pop(move, undo)
        self.assertEqual(signature(board), start)


class BotSearch(unittest.TestCase):
    def test_material_used_by_evaluation_and_capture_order_matches_ruleset(self):
        self.assertEqual(MATERIAL, (0, 20_000, 860, 480, 290, 235, 105, 20_000, 580, 285, 255, 85, 85, 65))
        self.assertEqual(BALANCED_MATERIAL, (0, 20_000, 860, 335, 155, 335, 100, 20_000, 640, 125, 190, 90, 170, 65))
        pieces = {square(0, 2): WK, square(8, 4): XK, square(2, 0): WR, square(2, 1): XR}
        classic = Board(pieces, turn=CHESS)
        balanced = Board(pieces, turn=CHESS, balanced=True)
        capture = Move(square(2, 0), square(2, 1))
        self.assertEqual(evaluate(balanced) - evaluate(classic), (335 - 480) - (640 - 580))
        self.assertEqual(Search._tactical_score(classic, capture), 16 * 580 - 480)
        self.assertEqual(Search._tactical_score(balanced.copy(), capture), 16 * 640 - 335)

    def test_quiescence_looks_past_a_poisoned_capture(self):
        board = position((2, 0, WQ), (2, 1, XN), (2, 2, XR))
        poisoned = Move(square(2, 0), square(2, 1))
        self.assertIn(poisoned, board.legal_moves())
        result = Search(table_bits=8).analyze(board, 1, max_depth=1)
        self.assertNotEqual(result.move, poisoned)

    def test_search_uses_cache_and_does_not_mutate_position(self):
        board = Board()
        start = signature(board)
        bot = Search(table_bits=12)
        result = bot.analyze(board, 2, max_depth=3)
        cached = bot.analyze(board, 2, max_depth=3)
        self.assertIn(result.move, board.legal_moves())
        self.assertEqual(result.depth, 3)
        self.assertEqual((cached.move, cached.score), (result.move, result.score))
        self.assertLess(cached.nodes, result.nodes)
        self.assertEqual(signature(board), start)

    def test_timeout_and_cancellation_keep_a_legal_fallback(self):
        board = Board()
        start = signature(board)
        bot = Search(table_bits=8)
        result = bot.analyze(board, .075)
        self.assertLess(result.elapsed, .3)
        self.assertIn(result.move, board.legal_moves())
        stop = Event()
        stop.set()
        canceled = bot.analyze(board, 10, cancel=stop)
        self.assertEqual(canceled.depth, 0)
        self.assertIn(canceled.move, board.legal_moves())
        self.assertEqual(signature(board), start)


if __name__ == "__main__":
    unittest.main()
