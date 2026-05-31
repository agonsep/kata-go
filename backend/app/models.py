"""Pydantic request/response schemas."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

# AI strength -> KataGo maxVisits per move.
AI_LEVELS = {"easy": 8, "medium": 96, "hard": 500, "max": 1500}


class NewGameRequest(BaseModel):
    boardSize: Literal[9, 13, 19] = 19
    humanColor: Literal["black", "white"] = "black"
    aiLevel: Literal["easy", "medium", "hard", "max"] = "medium"
    komi: float = 7.0


class MoveRequest(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class GameState(BaseModel):
    id: str
    boardSize: int
    board: list[list[int]]
    humanColor: str
    currentPlayer: str
    captures: dict[str, int]
    moveCount: int
    lastMove: Optional[dict] = None  # {"x": int, "y": int} or {"pass": True}
    status: str  # "playing" | "finished"
    result: Optional[str] = None
    blackWinrate: Optional[float] = None  # 0..1, Black's perspective
    blackScoreLead: Optional[float] = None  # points, Black's perspective
    aiLevel: str
    komi: float
    history: list[dict] = []


class HintResponse(BaseModel):
    x: Optional[int] = None
    y: Optional[int] = None
    isPass: bool = False
    blackWinrate: Optional[float] = None
