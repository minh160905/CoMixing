"""Stateless game API for Vercel and the local browser preview."""

from functools import cache
from http.server import BaseHTTPRequestHandler
import json

from co_xam.board import (
    Board, PIECE_NAMES, SIDE, SIDE_NAMES, SIZE, SQUARES, WESTERN_PALACE,
    CHECKMATE, STALEMATE, REPETITION, NO_PROGRESS, coordinates,
)
from co_xam.premove import _CASTLES, MAX_PREMOVES, possible_moves
from co_xam.search import Search

MAX_BODY = 96 * 1024
MAX_HISTORY = 4096
TIME_OPTIONS = (1, 3, 8)
REASONS = {
    CHECKMATE: "Chiếu hết",
    STALEMATE: "Hết nước hợp lệ",
    REPETITION: "Thế cờ lặp lại ba lần",
    NO_PROGRESS: "100 lượt không bắt quân và không đi Tốt",
}


def move_key(move):
    return [move.src, move.dst, move.promotion]


@cache
def client_config():
    cells = [0] * SIZE
    geometry = [None]
    for piece in range(1, len(SIDE)):
        routes = [[] for _ in cells]
        for src in SQUARES:
            cells[src] = piece
            routes[src] = [[move.dst, move.promotion] for move in possible_moves(cells, 0, src)]
            cells[src] = 0
        geometry.append(routes)
    return {
        "pieces": PIECE_NAMES,
        "sides": SIDE_NAMES,
        "sideByPiece": SIDE,
        "coords": {sq: coordinates(sq) for sq in SQUARES},
        "palace": sorted(WESTERN_PALACE),
        "geometry": geometry,
        "castles": [
            {"right": right, "move": move_key(move), "rook": [move.rook_from, move.rook_to]}
            for right, move in _CASTLES
        ],
        "maxPremoves": MAX_PREMOVES,
    }


def lookup_move(key, legal):
    if not isinstance(key, list) or len(key) != 3 or any(type(x) is not int for x in key):
        raise ValueError("Dữ liệu nước đi không hợp lệ.")
    for move in legal:
        if key == move_key(move):
            return move
    raise ValueError("Nước đi không hợp lệ trong thế cờ này.")


def record_move(board, move, records):
    undo = board.push_legal(move)
    records.append({
        "move": move_key(move), "piece": undo.piece, "capture": undo.capture,
        "castle": move.rook_from >= 0,
    })


def game_state(request):
    if not isinstance(request, dict):
        raise ValueError("Yêu cầu phải là một đối tượng JSON.")
    rules = request.get("rules", "classic")
    action = request.get("action", "state")
    history = request.get("history", [])
    if rules not in ("classic", "balanced") or action not in ("state", "move", "bot"):
        raise ValueError("Bộ luật hoặc thao tác không hợp lệ.")
    if not isinstance(history, list) or len(history) > MAX_HISTORY:
        raise ValueError("Lịch sử ván cờ không hợp lệ.")
    seconds = request.get("seconds", 3)
    if action == "bot" and (type(seconds) is not int or seconds not in TIME_OPTIONS):
        raise ValueError("Thời gian bot phải là 1, 3 hoặc 8 giây.")

    board = Board(balanced=rules == "balanced")
    records = []
    legal = board.legal_moves()
    for key in history:
        if board.outcome(legal):
            raise ValueError("Lịch sử có nước đi sau khi ván đã kết thúc.")
        record_move(board, lookup_move(key, legal), records)
        legal = board.legal_moves()

    outcome = board.outcome(legal)
    bot = None
    if action != "state":
        if outcome:
            raise ValueError("Ván cờ đã kết thúc.")
        if len(records) >= MAX_HISTORY:
            raise ValueError("Ván cờ đã đạt giới hạn lịch sử.")
        if action == "bot":
            result = Search(table_bits=15).analyze(board, seconds)
            move = result.move
            bot = {"depth": result.depth, "nodes": result.nodes}
        else:
            move = lookup_move(request.get("move"), legal)
        record_move(board, move, records)
        legal = board.legal_moves()
        outcome = board.outcome(legal)

    return {
        "rules": rules, "cells": board.cells, "turn": board.turn, "rights": board.rights,
        "check": board.kings[board.turn] if board.in_check() else None,
        "legal": [move_key(move) for move in legal] if outcome is None else [],
        "outcome": None if outcome is None else {"winner": outcome.winner, "reason": REASONS[outcome.reason]},
        "records": records, "bot": bot,
    }


class handler(BaseHTTPRequestHandler):
    def send_json(self, value, status=200, cache_control="no-store"):
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", cache_control)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self.send_json(client_config(), cache_control="public, max-age=300")

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.send_json({"error": "Kích thước yêu cầu không hợp lệ."}, 413)
                return
            request = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeError, RecursionError):
            self.send_json({"error": "Yêu cầu JSON không hợp lệ."}, 400)
            return

        try:
            response = game_state(request)
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)
            return
        self.send_json(response)
