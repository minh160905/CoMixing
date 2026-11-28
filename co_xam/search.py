"""Time-limited Negamax, alpha-beta pruning, and quiescence."""

from dataclasses import dataclass
from time import monotonic

from .board import CANNON_UNLOCK_PLY, XIANGQI, Move, SIZE, SQUARE_BITS
from .evaluation import MATERIAL, evaluate

MATE = 100_000
MATE_THRESHOLD = MATE - 500
INF = MATE + 1
EXACT, LOWER, UPPER = range(3)
MAX_Q_PLY = 12
EXPERT_SECONDS = 12
_UNVERIFIED_QUIET = object()


@dataclass(frozen=True, slots=True)
class SearchResult:
    move: Move | None
    score: int
    depth: int
    nodes: int
    elapsed: float


@dataclass(slots=True)
class Entry:
    key: int
    history_key: int
    quiet: int
    depth: int
    score: int
    flag: int
    move: Move | None
    generation: int


class SearchStopped(Exception):
    pass


class Search:
    def __init__(self, table_bits=17, *, expert=False):
        self.expert = expert
        self.table = [None] * (1 << table_bits)
        self.table_mask = len(self.table) - 1
        self.generation = 0

    def analyze(self, board, time_limit=2.0, cancel=None, max_depth=64):
        start = monotonic()
        self.deadline = start + max(0, time_limit)
        self.cancel = cancel
        self.nodes = 0
        legal = board.legal_moves()
        outcome = board.outcome(legal)
        if outcome is not None:
            score = 0 if outcome.winner is None else MATE if outcome.winner == board.turn else -MATE
            return SearchResult(None, score, 0, 0, monotonic() - start)
        self.generation += 1
        self.killers = [[None, None] for _ in range(max_depth + MAX_Q_PLY + 2)]
        self.history = [[0] * (SIZE * SIZE) for _ in range(2)]
        self.root_best = None
        best = max(legal, key=lambda move: self._tactical_score(board, move))
        score, completed = evaluate(board), 0
        for depth in range(1, max_depth + 1):
            try:
                self._check_time()
                value = self._search_root(board, depth, score)
            except SearchStopped:
                break
            best = self.root_best or best
            score, completed = value, depth
            if abs(score) >= MATE_THRESHOLD:
                break
        return SearchResult(best, score, completed, self.nodes, monotonic() - start)

    def _search_root(self, board, depth, previous):
        if not self.expert or depth < 3:
            return self._negamax(board, depth, -INF, INF, 0)
        margin = 48
        while True:
            self._check_time()
            alpha, beta = max(-INF, previous - margin), min(INF, previous + margin)
            score = self._negamax(board, depth, alpha, beta, 0)
            if alpha < score < beta:
                return score
            margin *= 2

    def _check_time(self):
        if monotonic() >= self.deadline or (self.cancel is not None and self.cancel.is_set()):
            raise SearchStopped

    def _visit(self):
        self.nodes += 1
        if self.nodes & 63 == 0:
            self._check_time()

    @staticmethod
    def _tactical_score(board, move):
        cells = board.cells
        victim = cells[move.dst]
        capture_score = 16 * MATERIAL[victim] - MATERIAL[cells[move.src]] if victim else 0
        promotion_score = 12 * MATERIAL[move.promotion] if move.promotion else 0
        return capture_score + promotion_score

    def _ordered_moves(self, board, ply, tt_move=None, tactical_only=False):
        moves = board.pseudo_moves(tactical_only)
        if tt_move is not None and tt_move in moves:
            yield tt_move, None
        tactical, quiet = [], []
        for move in moves:
            if move == tt_move:
                continue
            if board.cells[move.dst] or move.promotion:
                tactical.append(move)
            else:
                quiet.append(move)
        tactical.sort(key=lambda m: self._tactical_score(board, m), reverse=True)
        for move in tactical:
            yield move, None
        ordered = []
        killers = self.killers[ply]
        history = self.history[board.turn]
        direct, blockers = None, 0
        if (self.expert and len(quiet) >= 8
                and not (board.turn == XIANGQI and board.ply + 1 == CANNON_UNLOCK_PLY)
                and not board.in_check(1 - board.turn)):
            direct, blockers = board.check_candidates()
        for index, move in enumerate(quiet):
            if index & 15 == 15:
                self._check_time()
            if (direct is not None and move.rook_from < 0
                    and not (direct[board.cells[move.src]] & SQUARE_BITS[move.dst])
                    and not (blockers & (SQUARE_BITS[move.src] | SQUARE_BITS[move.dst]))):
                # Validate legality only if this quiet move survives ordering.
                checking = _UNVERIFIED_QUIET
            else:
                undo = board.push_legal(move)
                if undo is None:
                    continue
                checking = board.in_check()
                board.pop(move, undo)
            priority = 10_000 if move == killers[0] else 9_000 if move == killers[1] else 0
            priority += min(8_000, history[move.src * SIZE + move.dst])
            if checking is True:
                priority += 20_000
            ordered.append((priority, move, checking))
        ordered.sort(key=lambda pair: pair[0], reverse=True)
        for _, move, gives_check in ordered:
            yield move, gives_check

    @staticmethod
    def _play(board, move, gives_check):
        if gives_check is None or gives_check is _UNVERIFIED_QUIET:
            return board.push_legal(move)
        return board.push(move)

    def _entry(self, board):
        entry = self.table[board.key & self.table_mask]
        return entry if entry is not None and entry.key == board.key else None

    def _store(self, board, depth, score, flag, move, ply):
        index = board.key & self.table_mask
        old = self.table[index]
        if old is not None and old.generation == self.generation and old.depth > depth:
            return
        if score >= MATE_THRESHOLD:
            score += ply
        elif score <= -MATE_THRESHOLD:
            score -= ply
        self.table[index] = Entry(
            board.key, board.history_key, board.quiet, depth, score, flag, move, self.generation
        )

    def _negamax(self, board, depth, alpha, beta, ply):
        if depth == 0:
            return self._quiescence(board, alpha, beta, ply, 0)
        self._visit()
        if board.draw_reason() is not None:
            return ply - MATE if board.in_check() and not board.has_legal_move() else 0

        entry = self._entry(board)
        if (entry is not None and entry.depth >= depth and entry.history_key == board.history_key
                and entry.quiet == board.quiet):
            score = entry.score
            if score >= MATE_THRESHOLD:
                score -= ply
            elif score <= -MATE_THRESHOLD:
                score += ply
            if entry.flag == EXACT or (entry.flag == LOWER and score >= beta) or (
                entry.flag == UPPER and score <= alpha
            ):
                if ply == 0:
                    self.root_best = entry.move
                return score

        best, best_move = -INF, None
        start_alpha = alpha
        tt_move = entry.move if entry is not None else None
        legal_count = 0
        reduce_late = depth >= 3 and ply > 0 and not board.in_check()
        for move, gives_check in self._ordered_moves(board, ply, tt_move):
            undo = self._play(board, move, gives_check)
            if undo is None:
                continue
            legal_count += 1
            try:
                quiet_noncheck = gives_check is False or gives_check is _UNVERIFIED_QUIET
                if reduce_late and legal_count > 7 and quiet_noncheck and abs(alpha) < MATE_THRESHOLD:
                    # Verify any late quiet move that improves the reduced search.
                    score = -self._negamax(board, depth - 2, -alpha - 1, -alpha, ply + 1)
                    if score > alpha:
                        score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
                elif best_move is None or beta == alpha + 1:
                    score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
                else:
                    score = -self._negamax(board, depth - 1, -alpha - 1, -alpha, ply + 1)
                    if alpha < score < beta:
                        score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            finally:
                board.pop(move, undo)
            if score > best:
                best, best_move = score, move
            if score > alpha:
                alpha = score
            if alpha >= beta:
                if not undo.capture and not move.promotion and move != self.killers[ply][0]:
                    self.killers[ply][1] = self.killers[ply][0]
                    self.killers[ply][0] = move
                    self.history[board.turn][move.src * SIZE + move.dst] += depth * depth
                break
        if best_move is None:
            return ply - MATE if board.in_check() else 0
        if ply == 0:
            self.root_best = best_move
        flag = LOWER if best >= beta else UPPER if best <= start_alpha else EXACT
        self._store(board, depth, best, flag, best_move, ply)
        return best

    def _quiescence(self, board, alpha, beta, ply, q_ply):
        self._visit()
        in_check = board.in_check()
        if board.draw_reason() is not None:
            return ply - MATE if in_check and not board.has_legal_move() else 0
        if q_ply >= MAX_Q_PLY:
            if not board.has_legal_move():
                return ply - MATE if in_check else 0
            return evaluate(board)

        if in_check:
            best = -INF
        else:
            if not board.has_legal_move():
                return 0
            best = evaluate(board)
            if best >= beta:
                return best
            alpha = max(alpha, best)
        for move, gives_check in self._ordered_moves(board, ply, tactical_only=not in_check):
            undo = self._play(board, move, gives_check)
            if undo is None:
                continue
            try:
                score = -self._quiescence(board, -beta, -alpha, ply + 1, q_ply + 1)
            finally:
                board.pop(move, undo)
            if score >= beta:
                return score
            best = max(best, score)
            alpha = max(alpha, score)
        return ply - MATE if best == -INF else best
