"""Rules and incremental state for the hybrid board."""

from dataclasses import dataclass
from random import Random

CHESS, XIANGQI = range(2)
EMPTY, WK, WQ, WR, WB, WN, WP, XK, XR, XC, XN, XE, XA, XP = range(14)
SIDE = (-1,) + (CHESS,) * 6 + (XIANGQI,) * 7
FILES, RANKS = 9, 9
SIZE = FILES * RANKS
SQUARE_BITS = tuple(1 << sq for sq in range(SIZE))
RIVER = 4
PALACE_CENTER = 7 * FILES + 4
WESTERN_PALACE = frozenset(row * FILES + col for row in range(3) for col in range(2, 6))
CANNON_UNLOCK_PLY = 5
SQUARES = tuple(sq for sq in range(SIZE) if sq // FILES >= RIVER or sq % FILES < 8)
ORTHOGONAL = ((-1, 0), (1, 0), (0, -1), (0, 1))
DIAGONAL = ((-1, -1), (-1, 1), (1, -1), (1, 1))
KNIGHT = ((-2, -1), (-2, 1), (2, -1), (2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2))
PROMOTIONS = (WQ, WR, WB, WN)
QUEENSIDE, KINGSIDE = 1, 2
CHECKMATE, STALEMATE, REPETITION, NO_PROGRESS = range(1, 5)
PIECE_NAMES = (
    "", "Vua", "Hậu", "Xe", "Tượng", "Mã", "Tốt",
    "Tướng", "Xe", "Pháo", "Mã", "Tượng", "Sĩ", "Tốt",
)
SIDE_NAMES = ("Cờ vua", "Cờ tướng")


def square(row, col):
    return row * FILES + col


def coordinates(sq):
    row, col = divmod(sq, FILES)
    if row < RIVER:
        return f"{'abcdefgh'[col]}{8 - row}"
    return f"{9 - col}/{9 - row}"


def _landings(row, col, dr, dc):
    """Follow the source half's geometry and stop a crossing at the bank."""
    target_row, target_col = row + dr, col + dc
    western = row < RIVER
    if not 0 <= target_row < RANKS or not 0 <= target_col < (8 if western else 9):
        return ()
    if western == (target_row < RIVER):
        return (square(target_row, target_col),)
    if western:
        return (square(RIVER, target_col), square(RIVER, target_col + 1))
    return tuple(square(RIVER - 1, c) for c in (target_col - 1, target_col) if 0 <= c < 8)


def _inside_palace(sq):
    row, col = divmod(sq, FILES)
    return row >= 6 and 3 <= col <= 5


def _jump_routes(piece, src):
    row, col = divmod(src, FILES)
    if piece in (WK, XK):
        directions = ORTHOGONAL + DIAGONAL
    elif piece in (WN, XN):
        directions = KNIGHT
    elif piece == XA:
        directions = DIAGONAL
    elif piece == XE:
        directions = tuple((2 * dr, 2 * dc) for dr, dc in DIAGONAL)
    elif piece == XP:
        directions = ((-1, 0), (0, -1), (0, 1)) if row < RIVER else ((-1, 0),)
    elif piece == WP:
        if row == RIVER - 1:
            # The crossing uses only the empty forward landings.
            return ()
        directions = ((1, -1), (1, 1))
    else:
        return ()

    routes = {}
    for dr, dc in directions:
        for dst in _landings(row, col, dr, dc):
            if piece in (XK, XA):
                if not _inside_palace(src) or not _inside_palace(dst):
                    continue
                if piece == XK and dr and dc and PALACE_CENTER not in (src, dst):
                    continue
            if piece == XE and (row < RIVER or dst // FILES < RIVER or row + dr < RIVER):
                continue
            blocker = -1
            if piece == XE:
                blocker = square(row + dr // 2, col + dc // 2)
            elif piece in (WN, XN) and row >= RIVER:
                leg_row = row + (dr // 2 if abs(dr) == 2 else 0)
                leg_col = col + (dc // 2 if abs(dc) == 2 else 0)
                if leg_row >= RIVER:
                    blocker = square(leg_row, leg_col)
                else:
                    offset = dst % FILES - (col + dc)
                    mapped_col = leg_col + offset
                    if 0 <= mapped_col < 8:
                        blocker = square(RIVER - 1, mapped_col)
            routes[dst, blocker] = None
    return tuple(routes)


JUMPS = [[()] * SIZE for _ in SIDE]
MULTIPLE_ROUTES = [[False] * SIZE for _ in SIDE]
FORWARD = [()] * SIZE
RAYS = [[()] * SIZE for _ in SIDE]
JUMP_ATTACKS = [[[] for _ in range(SIZE)] for _ in range(2)]
RAY_ATTACKS = [[[] for _ in range(SIZE)] for _ in range(2)]


def _build_geometry():
    directional_pieces = (WQ, WR, WB, XR, XC)
    for src in SQUARES:
        row, col = divmod(src, FILES)
        FORWARD[src] = _landings(row, col, 1, 0)
        for piece in range(1, len(SIDE)):
            JUMPS[piece][src] = _jump_routes(piece, src)
            destinations = JUMPS[piece][src]
            MULTIPLE_ROUTES[piece][src] = len({dst for dst, _ in destinations}) < len(destinations)
            for dst, blocker in destinations:
                JUMP_ATTACKS[SIDE[piece]][dst].append((src, piece, blocker))
        for dr, dc in ORTHOGONAL + DIAGONAL:
            straight = dr == 0 or dc == 0
            ray = []
            for distance in range(1, RANKS):
                destinations = _landings(row, col, dr * distance, dc * distance)
                if not destinations:
                    break
                ray.append(destinations)
                if (row < RIVER) != (destinations[0] // FILES < RIVER):
                    break
            if not ray:
                continue
            for piece in directional_pieces:
                if (straight and piece == WB) or (not straight and piece in (WR, XR, XC)):
                    continue
                limit = 2 if row >= RIVER and piece in (WQ, WB) else len(ray)
                RAYS[piece][src] += (tuple(ray[:limit]),)
            path = 0
            for index, group in enumerate(ray):
                western_mask = 1 << WR if straight else 0
                if row < RIVER or index < 2:
                    western_mask |= (1 << WQ) | (0 if straight else 1 << WB)
                for dst in group:
                    if western_mask:
                        RAY_ATTACKS[CHESS][dst].append((src, western_mask, path))
                    if straight:
                        RAY_ATTACKS[XIANGQI][dst].append((src, (1 << XR) | (1 << XC), path))
                for dst in group:
                    path |= SQUARE_BITS[dst]
    for side in range(2):
        for routes in RAY_ATTACKS[side]:
            routes.sort(key=lambda route: route[2].bit_count())


_build_geometry()

PALACE_KING_JUMPS = tuple(
    tuple(route for route in JUMPS[WK][src] if route[0] in WESTERN_PALACE)
    if src in WESTERN_PALACE else ()
    for src in range(SIZE)
)

_rng = Random(0xC0A9)
_PIECE_KEYS = tuple(tuple(_rng.getrandbits(64) for _ in range(SIZE)) for _ in SIDE)
_SIDE_KEY = _rng.getrandbits(64)
_CASTLE_KEYS = tuple(_rng.getrandbits(64) for _ in range(4))
_OPENING_KEYS = tuple(_rng.getrandbits(64) for _ in range(CANNON_UNLOCK_PLY + 1))
_BALANCED_KEY = _rng.getrandbits(64)
_PIECE_BITS = tuple(1 << piece if piece else 0 for piece in range(len(SIDE)))


def _direct_attack_squares():
    squares = [[[0] * len(SIDE) for _ in range(SIZE)] for _ in range(2)]
    for side, targets in enumerate(squares):
        sliders = (WQ, WR, WB) if side == CHESS else (XR, XC)
        for target, pieces in enumerate(targets):
            for src, piece, _ in JUMP_ATTACKS[side][target]:
                pieces[piece] |= SQUARE_BITS[src]
            for src, mask, _ in RAY_ATTACKS[side][target]:
                for piece in sliders:
                    if mask & _PIECE_BITS[piece]:
                        pieces[piece] |= SQUARE_BITS[src]
    return squares


_DIRECT_ATTACK_SQUARES = _direct_attack_squares()
_HISTORY_SALT = 0x9E3779B97F4A7C15
_MASK_64 = (1 << 64) - 1


def _history_token(position_key, count):
    shifted = (position_key + count * _HISTORY_SALT) & _MASK_64
    return shifted ^ (shifted >> 27)


@dataclass(frozen=True, slots=True)
class Move:
    src: int
    dst: int
    promotion: int = EMPTY
    rook_from: int = -1
    rook_to: int = -1


@dataclass(slots=True)
class Undo:
    piece: int
    capture: int
    rights: int
    quiet: int
    key: int
    history_key: int
    previous_counts: dict | None
    occupied: int


@dataclass(frozen=True, slots=True)
class Outcome:
    winner: int | None
    reason: int


class Board:
    """A flat board with constant-time make/unmake and indexed piece locations."""

    def __init__(self, pieces=None, turn=XIANGQI, rights=None, ply=0, *, balanced=False):
        starting = pieces is None
        self.cells = [EMPTY] * SIZE
        self.occupied = 0
        self.positions = [set(), set()]
        self.kings = [-1, -1]
        self.turn = turn
        self.balanced = balanced
        self.rights = (QUEENSIDE | KINGSIDE if starting else 0) if rights is None else rights
        if balanced:
            self.rights &= QUEENSIDE
        self.ply = ply
        self.quiet = 0
        if starting:
            pieces = {
                **{square(0, c): p for c, p in enumerate((WR, WN, WB, WQ, WK, WB, WN, WR))},
                **{square(1, c): WP for c in range(8)},
                **{square(8, c): p for c, p in enumerate((XR, XN, XE, XA, XK, XA, XE, XN, XR))},
                **{square(6, c): XC for c in (1, 7)},
                **{square(5, c): XP for c in (0, 2, 4, 6, 8)},
            }
        self.key = _CASTLE_KEYS[self.rights] ^ _OPENING_KEYS[min(self.ply, CANNON_UNLOCK_PLY)]
        if balanced:
            self.key ^= _BALANCED_KEY
        if turn == XIANGQI:
            self.key ^= _SIDE_KEY
        for sq, piece in pieces.items():
            self.cells[sq] = piece
            if piece:
                self.occupied |= SQUARE_BITS[sq]
            self.positions[SIDE[piece]].add(sq)
            self.key ^= _PIECE_KEYS[piece][sq]
            if piece in (WK, XK):
                self.kings[SIDE[piece]] = sq
        self.counts = {self.key: 1}
        self.history_key = _history_token(self.key, 1)

    def copy(self):
        snapshot = object.__new__(Board)
        snapshot.cells = self.cells.copy()
        snapshot.occupied = self.occupied
        snapshot.positions = [p.copy() for p in self.positions]
        snapshot.kings = self.kings.copy()
        snapshot.turn = self.turn
        snapshot.balanced = self.balanced
        snapshot.rights = self.rights
        snapshot.ply = self.ply
        snapshot.quiet = self.quiet
        snapshot.key = self.key
        snapshot.counts = self.counts.copy()
        snapshot.history_key = self.history_key
        return snapshot

    def royals_face(self):
        western, eastern = self.kings
        wr, wc = divmod(western, FILES)
        er, ec = divmod(eastern, FILES)
        if er < RIVER or wr == er:
            return False
        aligned = wc in (ec - 1, ec) if wr < RIVER else wc == ec
        if not aligned:
            return False
        for row in range(min(wr, er) + 1, max(wr, er)):
            if row >= RIVER:
                if self.cells[square(row, ec)]:
                    return False
            elif (ec > 0 and self.cells[square(row, ec - 1)]) or (ec < 8 and self.cells[square(row, ec)]):
                return False
        return True

    def is_attacked(self, target, by_side):
        cells, occupied = self.cells, self.occupied
        for src, piece, blocker in JUMP_ATTACKS[by_side][target]:
            if cells[src] == piece and (blocker < 0 or not cells[blocker]):
                if self.balanced and piece == WK and (src not in WESTERN_PALACE or target not in WESTERN_PALACE):
                    continue
                return True
        if by_side == CHESS:
            for src, mask, path in RAY_ATTACKS[CHESS][target]:
                if mask & _PIECE_BITS[cells[src]] and not (path & occupied):
                    return True
        else:
            restricted = self.ply < CANNON_UNLOCK_PLY
            for src, mask, path in RAY_ATTACKS[XIANGQI][target]:
                piece = cells[src]
                if not (mask & _PIECE_BITS[piece]):
                    continue
                screens = path & occupied
                if piece == XR:
                    if not screens:
                        return True
                elif screens and not (screens & (screens - 1)):
                    if not restricted or SIDE[cells[screens.bit_length() - 1]] == XIANGQI:
                        return True
        return False

    def check_candidates(self):
        """Return masks for direct and discovered checks by the side to move."""
        side = self.turn
        target = self.kings[1 - side]
        cells = self.cells
        blockers = 0
        for src, piece, blocker in JUMP_ATTACKS[side][target]:
            if blocker >= 0 and cells[src] == piece:
                blockers |= SQUARE_BITS[blocker]
        for src, mask, path in RAY_ATTACKS[side][target]:
            if mask & _PIECE_BITS[cells[src]]:
                blockers |= path
        return _DIRECT_ATTACK_SQUARES[side][target], blockers

    def in_check(self, side=None):
        side = self.turn if side is None else side
        return self.is_attacked(self.kings[side], 1 - side)

    def threat_targets(self, src):
        """Return every square currently threatened/attacked by the piece at src."""
        cells = self.cells
        piece = cells[src]
        if not piece:
            return frozenset()
        side = SIDE[piece]
        targets = set()
        jumps = PALACE_KING_JUMPS[src] if self.balanced and piece == WK else JUMPS[piece][src]
        for dst, blocker in jumps:
            if blocker >= 0 and cells[blocker]:
                continue
            target = cells[dst]
            if not target or SIDE[target] != side:
                targets.add(dst)
        restricted = self.ply < CANNON_UNLOCK_PLY
        for ray in RAYS[piece][src]:
            screen = EMPTY
            for group in ray:
                for dst in group:
                    target = cells[dst]
                    if piece == XC:
                        if not (screen and (not restricted or SIDE[screen] == side)):
                            continue
                    if not target or SIDE[target] != side:
                        targets.add(dst)
                if len(group) == 1 and cells[group[0]]:
                    if piece != XC or screen:
                        break
                    screen = cells[group[0]]
        return frozenset(targets)

    def _castles(self):
        if not self.rights or self.in_check(CHESS):
            return
        cells = self.cells
        if self.rights & QUEENSIDE and cells[0] == WR and not (cells[1] or cells[2] or cells[3]):
            if not self.is_attacked(3, XIANGQI):
                yield Move(4, 2, rook_from=0, rook_to=3)
        if self.rights & KINGSIDE and cells[7] == WR and not (cells[5] or cells[6]):
            if not self.is_attacked(5, XIANGQI):
                yield Move(4, 6, rook_from=7, rook_to=5)

    def iter_pseudo_moves(self, tactical_only=False):
        cells = self.cells
        side = self.turn
        opposing_king = self.kings[1 - side]
        for src in tuple(self.positions[side]):
            piece = cells[src]
            if piece == WP:
                for dst in FORWARD[src]:
                    if cells[dst]:
                        continue
                    if dst // FILES == RANKS - 1:
                        yield from (Move(src, dst, promotion) for promotion in PROMOTIONS)
                    elif not tactical_only:
                        yield Move(src, dst)
                        if src // FILES == 1 and not cells[dst + FILES]:
                            yield Move(src, dst + FILES)
            used_destinations = set() if MULTIPLE_ROUTES[piece][src] else None
            jumps = PALACE_KING_JUMPS[src] if self.balanced and piece == WK else JUMPS[piece][src]
            for dst, blocker in jumps:
                target = cells[dst]
                if dst == opposing_king or target and SIDE[target] == side:
                    continue
                if (blocker >= 0 and cells[blocker]) or (not target and (tactical_only or piece == WP)):
                    continue
                if used_destinations is not None:
                    if dst in used_destinations:
                        continue
                    used_destinations.add(dst)
                if piece == WP and dst // FILES == RANKS - 1:
                    yield from (Move(src, dst, promotion) for promotion in PROMOTIONS)
                else:
                    yield Move(src, dst)
            # On the bank, adjacent queen rays can project to the same point.
            ray_destinations = set() if piece == WQ and src // FILES in (RIVER - 1, RIVER) else None
            for ray in RAYS[piece][src]:
                screen = EMPTY
                for group in ray:
                    for dst in group:
                        target = cells[dst]
                        if target:
                            if dst == opposing_king or SIDE[target] == side:
                                continue
                            if piece == XC and not (screen and (self.ply >= CANNON_UNLOCK_PLY or SIDE[screen] == side)):
                                continue
                        elif tactical_only or screen:
                            continue
                        if ray_destinations is not None:
                            if dst in ray_destinations:
                                continue
                            ray_destinations.add(dst)
                        yield Move(src, dst)
                    if len(group) == 1 and cells[group[0]]:
                        if piece != XC or screen:
                            break
                        screen = cells[group[0]]
            if not tactical_only and piece == WK and src == 4:
                yield from self._castles()

    def pseudo_moves(self, tactical_only=False):
        return list(self.iter_pseudo_moves(tactical_only))

    def push(self, move):
        """Make a move already known to be legal or being tested for legality."""
        src, dst = move.src, move.dst
        cells = self.cells
        piece, capture = cells[src], cells[dst]
        side = self.turn
        quiet = not capture and piece not in (WP, XP)
        reversible = quiet or (not capture and not move.promotion and src // FILES == dst // FILES)
        undo = Undo(piece, capture, self.rights, self.quiet, self.key, self.history_key, None, self.occupied)
        placed = move.promotion or piece
        cells[src], cells[dst] = EMPTY, placed
        self.occupied = (self.occupied ^ SQUARE_BITS[src]) | SQUARE_BITS[dst]
        self.positions[side].remove(src)
        self.positions[side].add(dst)
        key = self.key ^ _SIDE_KEY ^ _PIECE_KEYS[piece][src] ^ _PIECE_KEYS[placed][dst]
        if capture:
            self.positions[1 - side].remove(dst)
            key ^= _PIECE_KEYS[capture][dst]
        if piece in (WK, XK):
            self.kings[side] = dst
        if piece == WK:
            self.rights = 0
        elif piece == WR:
            self.rights &= ~(QUEENSIDE if src == 0 else KINGSIDE if src == 7 else 0)
        if capture == WR:
            self.rights &= ~(QUEENSIDE if dst == 0 else KINGSIDE if dst == 7 else 0)
        if move.rook_from >= 0:
            rook_from, rook_to = move.rook_from, move.rook_to
            cells[rook_from], cells[rook_to] = EMPTY, WR
            self.occupied ^= SQUARE_BITS[rook_from] | SQUARE_BITS[rook_to]
            self.positions[side].remove(rook_from)
            self.positions[side].add(rook_to)
            key ^= _PIECE_KEYS[WR][rook_from] ^ _PIECE_KEYS[WR][rook_to]
        if self.rights != undo.rights:
            key ^= _CASTLE_KEYS[undo.rights] ^ _CASTLE_KEYS[self.rights]
        self.ply += 1
        if self.ply <= CANNON_UNLOCK_PLY:
            key ^= _OPENING_KEYS[self.ply - 1] ^ _OPENING_KEYS[self.ply]
        self.key = key
        self.quiet = self.quiet + 1 if quiet else 0
        self.turn = 1 - side
        if not reversible or self.rights != undo.rights or self.ply <= CANNON_UNLOCK_PLY:
            undo.previous_counts = self.counts
            self.counts = {key: 1}
            self.history_key = _history_token(key, 1)
        else:
            count = self.counts.get(key, 0)
            self.counts[key] = count + 1
            if count:
                self.history_key ^= _history_token(key, count)
            self.history_key ^= _history_token(key, count + 1)
        return undo

    def push_legal(self, move):
        if self.balanced and self.cells[move.src] == WK and move.dst not in WESTERN_PALACE:
            return None
        undo = self.push(move)
        if self.in_check(1 - self.turn) or self.royals_face():
            self.pop(move, undo)
            return None
        return undo

    def pop(self, move, undo):
        if undo.previous_counts is not None:
            self.counts = undo.previous_counts
        else:
            count = self.counts[self.key]
            if count == 1:
                del self.counts[self.key]
            else:
                self.counts[self.key] = count - 1
        side = 1 - self.turn
        src, dst = move.src, move.dst
        self.cells[src], self.cells[dst] = undo.piece, undo.capture
        self.positions[side].remove(dst)
        self.positions[side].add(src)
        if undo.capture:
            self.positions[self.turn].add(dst)
        if undo.piece in (WK, XK):
            self.kings[side] = src
        if move.rook_from >= 0:
            self.cells[move.rook_to], self.cells[move.rook_from] = EMPTY, WR
            self.positions[side].remove(move.rook_to)
            self.positions[side].add(move.rook_from)
        self.turn, self.rights, self.quiet = side, undo.rights, undo.quiet
        self.key, self.history_key = undo.key, undo.history_key
        self.occupied = undo.occupied
        self.ply -= 1

    def legal_moves(self):
        legal = []
        for move in self.pseudo_moves():
            undo = self.push_legal(move)
            if undo is not None:
                self.pop(move, undo)
                legal.append(move)
        return legal

    def has_legal_move(self):
        for move in self.iter_pseudo_moves():
            undo = self.push_legal(move)
            if undo is not None:
                self.pop(move, undo)
                return True
        return False

    def draw_reason(self):
        if self.counts[self.key] >= 3:
            return REPETITION
        if self.quiet >= 100:
            return NO_PROGRESS
        return None

    def outcome(self, legal=None):
        if not (self.legal_moves() if legal is None else legal):
            if self.in_check():
                return Outcome(1 - self.turn, CHECKMATE)
            return Outcome(None, STALEMATE)
        reason = self.draw_reason()
        return Outcome(None, reason) if reason is not None else None
