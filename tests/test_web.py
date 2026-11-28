from unittest import TestCase
from unittest.mock import patch

from api.game import client_config, game_state
from co_xam.board import Board, EMPTY, SIZE, WK, WQ, XK, XP, WESTERN_PALACE, square
from co_xam.search import SearchResult


class WebGame(TestCase):
    def test_state_replays_legal_moves_and_reports_undo_state(self):
        first = [square(5, 0), square(4, 0), 0]
        start = game_state({"rules": "balanced"})
        self.assertIn(first, start["legal"])
        result = game_state({"rules": "balanced", "action": "move", "move": first})
        self.assertEqual(result["turn"], 0)
        self.assertEqual(result["records"][0]["move"], first)
        self.assertEqual(game_state({"rules": "balanced", "history": [first]}), result)
        self.assertEqual(game_state({"rules": "balanced", "history": []}), start)

    def test_bot_reports_the_move_from_the_shared_engine(self):
        move = Board().legal_moves()[0]
        with patch("api.game.Search") as search:
            search.return_value.analyze.return_value = SearchResult(move, 0, 3, 52, 1.0)
            result = game_state({"action": "bot", "seconds": 1})
        self.assertEqual(result["records"][0]["move"], [move.src, move.dst, move.promotion])
        self.assertEqual(result["bot"], {"depth": 3, "nodes": 52})
        self.assertEqual(search.return_value.analyze.call_args.args[1], 1)

    def test_invalid_request_or_move_is_rejected(self):
        for request in ([], {"rules": "unknown"}, {"history": [[26, 500, 0]]},
                        {"action": "move", "move": [45, 36, True]},
                        {"action": "bot", "seconds": 100}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                game_state(request)

    def test_browser_gets_shared_geometry_and_palace(self):
        config = client_config()
        self.assertEqual(set(config["palace"]), WESTERN_PALACE)
        self.assertIn([square(3, 5), 0], config["geometry"][WK][square(2, 5)])
        self.assertNotIn(square(3, 5), config["palace"])
        self.assertEqual(config["maxPremoves"], 5)

    def test_state_reports_piece_threats(self):
        start = game_state({"rules": "classic"})
        knight_b8 = str(square(0, 1))
        self.assertEqual(set(start["threats"][knight_b8]), {square(2, 0), square(2, 2)})
        cannon = str(square(6, 1))
        # Left cannon uses right cannon at (6, 7) as a friendly screen to threaten (6, 8).
        self.assertEqual(start["threats"][cannon], [square(6, 8)])

    def test_custom_practice_setup_state_and_moves(self):
        cells = [EMPTY] * SIZE
        cells[square(0, 4)] = WK
        cells[square(8, 4)] = XK
        cells[square(5, 4)] = XP
        cells[square(2, 2)] = WQ
        setup = {"cells": cells, "turn": 0, "ply": 5}
        state = game_state({"rules": "classic", "setup": setup})
        self.assertEqual(state["turn"], 0)
        move = [square(2, 2), square(2, 3), 0]
        self.assertIn(move, state["legal"])
        after = game_state({"rules": "classic", "setup": setup, "action": "move", "move": move})
        self.assertEqual(after["cells"][square(2, 3)], WQ)
        self.assertEqual(after["turn"], 1)

        # Invalid setup (facing royals) is rejected
        bad = cells.copy()
        bad[square(5, 4)] = EMPTY
        with self.assertRaises(ValueError):
            game_state({"rules": "classic", "setup": {"cells": bad, "turn": 0, "ply": 5}})
