"""FastAPI server: play Go against the KataGo engine."""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .goban import BLACK, WHITE, Goban, IllegalMove, opponent
from .katago import KataGoEngine, KataGoError
from .models import AI_LEVELS, GameState, HintResponse, MoveRequest, NewGameRequest

_COLS = "ABCDEFGHJKLMNOPQRST"
RULES = "chinese"
RESIGN_WINRATE = 0.04

engine = KataGoEngine()
games: dict[str, "Game"] = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await engine.start()
    yield
    await engine.stop()


app = FastAPI(title="KataGo Go", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _color_name(color):
    return "black" if color == BLACK else "white"


def _color_int(name):
    return BLACK if name == "black" else WHITE


def _xy_to_gtp(x, y, size):
    return Goban.to_gtp(x, y, size)


def _gtp_to_xy(coord, size):
    col = _COLS.index(coord[0].upper())
    row = int(coord[1:])
    return col, size - row


class Game:
    def __init__(self, req: NewGameRequest):
        self.id = uuid.uuid4().hex[:12]
        self.board_size = req.boardSize
        self.komi = req.komi
        self.ai_level = req.aiLevel
        self.ai_visits = AI_LEVELS[req.aiLevel]
        self.human_color = _color_int(req.humanColor)
        self.ai_color = opponent(self.human_color)
        self.goban = Goban(req.boardSize)
        self.moves = []  # list of (color, x, y); x is None for a pass
        self.current = BLACK
        self.status = "playing"
        self.result = None
        self.last_move = None
        self.black_winrate = None
        self.black_score = None

    def katago_moves(self):
        out = []
        for color, x, y in self.moves:
            c = "B" if color == BLACK else "W"
            out.append([c, "pass" if x is None else _xy_to_gtp(x, y, self.board_size)])
        return out

    def double_pass(self):
        return (
            len(self.moves) >= 2
            and self.moves[-1][1] is None
            and self.moves[-2][1] is None
        )

    def state(self) -> GameState:
        return GameState(
            id=self.id,
            boardSize=self.board_size,
            board=self.goban.as_list(),
            humanColor=_color_name(self.human_color),
            currentPlayer=_color_name(self.current),
            captures={
                "black": self.goban.captures[BLACK],
                "white": self.goban.captures[WHITE],
            },
            moveCount=len(self.moves),
            lastMove=self.last_move,
            status=self.status,
            result=self.result,
            blackWinrate=self.black_winrate,
            blackScoreLead=self.black_score,
            aiLevel=self.ai_level,
            komi=self.komi,
        )


def _store_eval(game: Game, root: dict):
    """Record win/score from KataGo rootInfo.

    The analysis config has `reportAnalysisWinratesAs = BLACK`, so winrate and
    scoreLead are already from Black's perspective — no conversion needed.
    """
    game.black_winrate = root.get("winrate")
    game.black_score = root.get("scoreLead")


async def _score_game(game: Game):
    resp = await engine.analyze(
        game.katago_moves(), game.board_size, game.komi, RULES, 100
    )
    _store_eval(game, resp.get("rootInfo", {}))
    score = game.black_score or 0.0
    if score >= 0:
        winner, margin = "Black", score
    else:
        winner, margin = "White", -score
    game.status = "finished"
    game.result = f"{winner} wins by {margin:.1f} points"


async def _ai_turn(game: Game):
    """Run one AI move (analysis, then play / pass / resign)."""
    resp = await engine.analyze(
        game.katago_moves(), game.board_size, game.komi, RULES, game.ai_visits
    )
    root = resp.get("rootInfo", {})
    _store_eval(game, root)

    # rootInfo.winrate is from Black's perspective; flip if AI is White.
    black_winrate = root.get("winrate", 0.5)
    ai_winrate = black_winrate if game.ai_color == BLACK else 1.0 - black_winrate
    if len(game.moves) >= 2 * game.board_size and ai_winrate < RESIGN_WINRATE:
        game.status = "finished"
        game.result = f"{_color_name(game.human_color).capitalize()} wins by resignation"
        return

    infos = sorted(resp.get("moveInfos", []), key=lambda m: m.get("order", 999))
    move = infos[0]["move"] if infos else "pass"

    if move == "pass":
        game.goban.play_pass()
        game.moves.append((game.ai_color, None, None))
        game.last_move = {"pass": True}
    else:
        x, y = _gtp_to_xy(move, game.board_size)
        game.goban.play(game.ai_color, x, y)
        game.moves.append((game.ai_color, x, y))
        game.last_move = {"x": x, "y": y}

    game.current = game.human_color
    if game.double_pass():
        await _score_game(game)


def _get_game(game_id: str) -> Game:
    game = games.get(game_id)
    if game is None:
        raise HTTPException(404, "game not found")
    return game


@app.get("/api/health")
async def health():
    running = engine.proc is not None and engine.proc.returncode is None
    return {"ok": running}


@app.post("/api/games", response_model=GameState)
async def new_game(req: NewGameRequest):
    game = Game(req)
    games[game.id] = game
    if game.human_color == WHITE:  # AI is Black, moves first
        try:
            await _ai_turn(game)
        except KataGoError as e:
            raise HTTPException(503, str(e))
    return game.state()


@app.get("/api/games/{game_id}", response_model=GameState)
async def get_game(game_id: str):
    return _get_game(game_id).state()


@app.post("/api/games/{game_id}/move", response_model=GameState)
async def play_move(game_id: str, req: MoveRequest):
    game = _get_game(game_id)
    if game.status != "playing":
        raise HTTPException(409, "game is over")
    if game.current != game.human_color:
        raise HTTPException(409, "not your turn")
    try:
        game.goban.play(game.human_color, req.x, req.y)
    except IllegalMove as e:
        raise HTTPException(400, str(e))
    game.moves.append((game.human_color, req.x, req.y))
    game.last_move = {"x": req.x, "y": req.y}
    game.current = game.ai_color
    try:
        await _ai_turn(game)
    except KataGoError as e:
        raise HTTPException(503, str(e))
    return game.state()


@app.post("/api/games/{game_id}/pass", response_model=GameState)
async def pass_move(game_id: str):
    game = _get_game(game_id)
    if game.status != "playing":
        raise HTTPException(409, "game is over")
    if game.current != game.human_color:
        raise HTTPException(409, "not your turn")
    game.goban.play_pass()
    game.moves.append((game.human_color, None, None))
    game.last_move = {"pass": True}
    game.current = game.ai_color
    try:
        if game.double_pass():
            await _score_game(game)
        else:
            await _ai_turn(game)
    except KataGoError as e:
        raise HTTPException(503, str(e))
    return game.state()


@app.post("/api/games/{game_id}/resign", response_model=GameState)
async def resign(game_id: str):
    game = _get_game(game_id)
    if game.status != "playing":
        raise HTTPException(409, "game is over")
    game.status = "finished"
    game.result = f"{_color_name(game.ai_color).capitalize()} wins by resignation"
    return game.state()


@app.post("/api/games/{game_id}/hint", response_model=HintResponse)
async def hint(game_id: str):
    game = _get_game(game_id)
    if game.status != "playing":
        raise HTTPException(409, "game is over")
    if game.current != game.human_color:
        raise HTTPException(409, "not your turn")
    try:
        resp = await engine.analyze(
            game.katago_moves(), game.board_size, game.komi, RULES, 400
        )
    except KataGoError as e:
        raise HTTPException(503, str(e))
    infos = sorted(resp.get("moveInfos", []), key=lambda m: m.get("order", 999))
    root = resp.get("rootInfo", {})
    black_wr = root.get("winrate")  # already from Black's perspective
    if not infos or infos[0]["move"] == "pass":
        return HintResponse(isPass=True, blackWinrate=black_wr)
    x, y = _gtp_to_xy(infos[0]["move"], game.board_size)
    return HintResponse(x=x, y=y, blackWinrate=black_wr)
