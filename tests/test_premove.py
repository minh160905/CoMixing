import unittest

from co_xam.board import Board, CHESS, XIANGQI, EMPTY, WK, WN, WP, WQ, WR, XC, XR, Move, square
from co_xam.premove import MAX_PREMOVES, PremoveQueue, possible_moves
from tests.test_game import position


class PremoveRules(unittest.TestCase):
    def test_planning_and_playing_two_moves_in_order(self):
        board = Board()
        queue = PremoveQueue()
        first = Move(square(0, 1), square(2, 2))
        second = Move(square(2, 2), square(4, 3))
        self.assertTrue(queue.add(WN, first))
        cells, rights = queue.project(board)
        self.assertEqual(board.cells[first.src], WN)
        self.assertEqual(cells[first.src], EMPTY)
        self.assertIn(second, possible_moves(cells, rights, first.dst))
        self.assertTrue(queue.add(WN, second))

        board.push_legal(Move(square(5, 0), square(4, 0)))
        self.assertEqual(queue.take(board, board.legal_moves()), first)
        self.assertIsNotNone(board.push_legal(first))
        board.push_legal(Move(square(4, 0), square(3, 0)))
        self.assertEqual(queue.take(board, board.legal_moves()), second)
        self.assertFalse(queue)

    def test_capture_of_premoved_piece_cancels_dependent_moves(self):
        board = position((2, 1, XR), (2, 2, WN), turn=XIANGQI)
        queue = PremoveQueue()
        queue.add(WN, Move(square(2, 2), square(4, 3)))
        queue.add(WN, Move(square(4, 3), square(5, 5)))
        capture = Move(square(2, 1), square(2, 2))
        self.assertIsNotNone(board.push_legal(capture))
        self.assertIsNone(queue.take(board, board.legal_moves()))
        self.assertFalse(queue)

    def test_speculative_capture_checks_occupancy_when_played(self):
        src = square(6, 3)
        dst = square(7, 4)
        move = Move(src, dst)
        board = position((6, 3, WP), turn=CHESS)
        self.assertIn(move, possible_moves(board.cells, board.rights, src))
        queue = PremoveQueue()
        queue.add(WP, move)
        self.assertIsNone(queue.take(board, board.legal_moves()))
        occupied = position((6, 3, WP), (7, 4, XC), turn=CHESS)
        queue.add(WP, move)
        self.assertEqual(queue.take(occupied, occupied.legal_moves()), move)

    def test_western_king_planning_uses_balanced_palace(self):
        cells = Board().cells
        cells[4] = WK
        cells[0] = cells[7] = WR
        choices = possible_moves(cells, 3, 4, balanced=True)
        self.assertIn(Move(4, 2, rook_from=0, rook_to=3), choices)
        self.assertNotIn(Move(4, 6, rook_from=7, rook_to=5), choices)
        cells[4] = EMPTY
        origin = square(2, 5)
        cells[origin] = WK
        choices = possible_moves(cells, 0, origin, balanced=True)
        self.assertIn(Move(origin, square(2, 4)), choices)
        self.assertNotIn(Move(origin, square(2, 6)), choices)
        self.assertNotIn(Move(origin, square(3, 5)), choices)

    def test_promotion_choices_and_queue_limit(self):
        src, dst = square(7, 2), square(8, 2)
        board = position((7, 2, WP), turn=CHESS)
        move = Move(src, dst, WQ)
        self.assertIn(move, possible_moves(board.cells, board.rights, src))
        queue = PremoveQueue()
        for _ in range(MAX_PREMOVES):
            self.assertTrue(queue.add(WP, move))
        self.assertFalse(queue.add(WP, move))
        cells, _ = queue.project(board)
        self.assertEqual(cells[dst], WQ)
