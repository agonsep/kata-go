"""Minimal Go rules engine: captures, suicide, simple ko."""

EMPTY, BLACK, WHITE = 0, 1, 2
_COLS = "ABCDEFGHJKLMNOPQRST"  # GTP columns skip 'I'


class IllegalMove(Exception):
    pass


def opponent(color):
    return WHITE if color == BLACK else BLACK


class Goban:
    def __init__(self, size):
        self.size = size
        self.grid = [[EMPTY] * size for _ in range(size)]
        self.ko = None  # point forbidden by simple ko, or None
        self.captures = {BLACK: 0, WHITE: 0}  # stones each color has captured

    def _neighbors(self, x, y):
        if x > 0:
            yield x - 1, y
        if x < self.size - 1:
            yield x + 1, y
        if y > 0:
            yield x, y - 1
        if y < self.size - 1:
            yield x, y + 1

    def _group(self, x, y):
        """Return (set of stones in group, set of liberty points)."""
        color = self.grid[y][x]
        stack = [(x, y)]
        stones = {(x, y)}
        liberties = set()
        while stack:
            cx, cy = stack.pop()
            for nx, ny in self._neighbors(cx, cy):
                v = self.grid[ny][nx]
                if v == EMPTY:
                    liberties.add((nx, ny))
                elif v == color and (nx, ny) not in stones:
                    stones.add((nx, ny))
                    stack.append((nx, ny))
        return stones, liberties

    def play(self, color, x, y):
        """Apply a stone. Returns number of captured stones. Raises IllegalMove."""
        if not (0 <= x < self.size and 0 <= y < self.size):
            raise IllegalMove("off board")
        if self.grid[y][x] != EMPTY:
            raise IllegalMove("point is occupied")
        if self.ko == (x, y):
            raise IllegalMove("illegal ko recapture")

        opp = opponent(color)
        self.grid[y][x] = color

        captured = set()
        for nx, ny in self._neighbors(x, y):
            if self.grid[ny][nx] == opp:
                stones, liberties = self._group(nx, ny)
                if not liberties:
                    captured |= stones
        for cx, cy in captured:
            self.grid[cy][cx] = EMPTY

        stones, liberties = self._group(x, y)
        if not liberties:
            # suicide: undo and reject
            self.grid[y][x] = EMPTY
            for cx, cy in captured:
                self.grid[cy][cx] = opp
            raise IllegalMove("suicide is not allowed")

        self.captures[color] += len(captured)
        # simple ko: a single stone captured a single stone that now has one liberty
        if len(captured) == 1 and len(stones) == 1 and len(liberties) == 1:
            self.ko = next(iter(captured))
        else:
            self.ko = None
        return len(captured)

    def play_pass(self):
        self.ko = None

    def as_list(self):
        return [row[:] for row in self.grid]

    @staticmethod
    def to_gtp(x, y, size):
        """Convert (x, y) grid coords (y=0 is the top row) to a GTP coordinate."""
        return f"{_COLS[x]}{size - y}"
