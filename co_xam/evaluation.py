"""Material and interpolated opening, middlegame, and endgame tables."""

from .board import (
    CHESS, FILES, RIVER, SIDE, SIZE, SQUARES,
    WK, WQ, WR, WB, WN, WP, XK, XR, XC, XN, XE, XA, XP,
)

MATERIAL = (0, 20_000, 900, 510, 330, 325, 100, 20_000, 555, 445, 335, 190, 175, 105)
PHASE_WEIGHT = (0, 0, 4, 2, 1, 1, 0, 0, 2, 2, 1, 1, 1, 0)
OPENING_PHASE = 26
MIDDLE_PHASE = 16


def _position_scores(piece, row, col):
    column = 2 * col + int(row < RIVER)
    center_file = 8 - abs(8 - column)
    center = center_file + 2 * (4 - abs(4 - row))
    if piece == WK:
        castle_bonus = 24 if row == 0 and col in (2, 6) else 0
        return castle_bonus - 18 * row, castle_bonus - 15 * row, 5 * center
    if piece == XK:
        return (18 if row == 8 else -12 * (8 - row),
                12 if row == 8 else -8 * (8 - row),
                8 * (8 - row) + center_file)
    if piece == WP:
        progress = row - 1
        return (center_file * 3 + 6 * progress,
                center_file * 2 + 9 * progress,
                center_file + 12 * progress + (26 if row == 7 else 0))
    if piece == XP:
        progress = 5 - row
        crossed = 13 if row < RIVER else 0
        return (center_file + 6 * progress + crossed,
                center_file * 2 + 8 * progress + crossed,
                center_file * 2 + 9 * progress + crossed - (16 if row == 0 else 0))
    if piece in (WN, XN):
        home = row == (0 if piece == WN else 8)
        horse_leg_cost = 12 if row >= RIVER else 0
        return (4 * center - 18 * home - horse_leg_cost,
                4 * center - horse_leg_cost, 3 * center - horse_leg_cost)
    if piece == WB:
        range_cost = 26 if row >= RIVER else 0
        return (3 * center - 16 * (row == 0) - range_cost,
                3 * center - range_cost, 2 * center - range_cost)
    if piece == WQ:
        range_cost = 90 if row >= RIVER else 0
        return (center - 9 * row - range_cost, 2 * center - range_cost, 3 * center - range_cost)
    if piece in (WR, XR):
        progress = row if piece == WR else 8 - row
        return center_file + 2 * progress, center_file + 4 * progress, center + 4 * progress
    if piece == XC:
        return 3 * center, 4 * center, 2 * center
    if piece == XE:
        return 2 * center + 8 * (row == 6), 2 * center + 8 * (row == 6), center
    return center_file + 5 * (row == 7), center_file + 5 * (row == 7), center_file


PIECE_SQUARE_TABLES = [[[0] * SIZE for _ in SIDE] for _ in range(3)]
for piece in range(1, len(SIDE)):
    for sq in SQUARES:
        for stage, positional_score in enumerate(_position_scores(piece, *divmod(sq, FILES))):
            PIECE_SQUARE_TABLES[stage][piece][sq] = positional_score

# Store the signed material contribution together with each positional term.
_SIGNED_TABLES = tuple(
    tuple(
        tuple((MATERIAL[piece] + score) * (1 if SIDE[piece] == CHESS else -1) for score in row)
        for piece, row in enumerate(phase_table)
    )
    for phase_table in PIECE_SQUARE_TABLES
)


def evaluate(board):
    """Return a centipawn-like score from the current player's perspective."""
    cells = board.cells
    opening, middle, endgame = _SIGNED_TABLES
    phase = opening_score = middle_score = endgame_score = 0
    for locations in board.positions:
        for sq in locations:
            piece = cells[sq]
            phase += PHASE_WEIGHT[piece]
            opening_score += opening[piece][sq]
            middle_score += middle[piece][sq]
            endgame_score += endgame[piece][sq]

    phase = min(OPENING_PHASE, phase)
    if phase >= MIDDLE_PHASE:
        score = (opening_score * (phase - MIDDLE_PHASE) + middle_score * (OPENING_PHASE - phase))
        score //= OPENING_PHASE - MIDDLE_PHASE
    else:
        score = (middle_score * phase + endgame_score * (MIDDLE_PHASE - phase)) // MIDDLE_PHASE
    return (score if board.turn == CHESS else -score) + 8
