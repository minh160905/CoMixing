"""Speculative player input that is checked against each real position."""

from .board import (
    EMPTY, FILES, FORWARD, JUMPS, KINGSIDE, PROMOTIONS, QUEENSIDE,
    RANKS, RAYS, WK, WP, WR, Move,
)

MAX_PREMOVES = 5
_CASTLES = (
    (QUEENSIDE, Move(4, 2, rook_from=0, rook_to=3)),
    (KINGSIDE, Move(4, 6, rook_from=7, rook_to=5)),
)


def possible_moves(cells, rights, src):
    """Offer geometrically possible moves before the opponent has played."""
    piece = cells[src]
    if not piece:
        return ()
    destinations = {dst for dst, _ in JUMPS[piece][src]}
    for ray in RAYS[piece][src]:
        for group in ray:
            destinations.update(group)
    if piece == WP:
        destinations.update(FORWARD[src])
        if src // FILES == 1:
            destinations.add(src + 2 * FILES)
    choices = []
    for dst in sorted(destinations):
        if piece == WP and dst // FILES == RANKS - 1:
            choices.extend(Move(src, dst, promotion) for promotion in PROMOTIONS)
        else:
            choices.append(Move(src, dst))
    if piece == WK and src == 4:
        choices.extend(move for flag, move in _CASTLES if rights & flag and cells[move.rook_from] == WR)
    return tuple(choices)


class PremoveQueue:
    def __init__(self):
        self._entries = []

    def __len__(self):
        return len(self._entries)

    @property
    def moves(self):
        return tuple(move for _, move in self._entries)

    def clear(self):
        self._entries.clear()

    def add(self, piece, move):
        if len(self) >= MAX_PREMOVES:
            return False
        self._entries.append((piece, move))
        return True

    def project(self, board):
        """Preview what the board would look like after the queued player moves."""
        cells, rights = board.cells.copy(), board.rights
        for piece, move in self._entries:
            if cells[move.src] != piece:
                break
            if piece == WK:
                rights = 0
            for sq in (move.src, move.dst):
                if cells[sq] == WR:
                    rights &= ~(QUEENSIDE if sq == 0 else KINGSIDE if sq == 7 else 0)
            cells[move.src], cells[move.dst] = EMPTY, move.promotion or piece
            if move.rook_from >= 0:
                cells[move.rook_from], cells[move.rook_to] = EMPTY, WR
        return cells, rights

    def take(self, board, legal_moves):
        """Consume the next request after the opponent's move."""
        piece, move = self._entries.pop(0)
        if board.cells[move.src] == piece and move in legal_moves:
            return move
        self.clear()
        return None
