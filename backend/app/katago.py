"""Async wrapper around the KataGo analysis engine (JSON over stdin/stdout)."""

import asyncio
import json
import os
import shutil
import subprocess

# Resolve KataGo paths. Env vars override; defaults target a Homebrew install.
_BREW_SHARE = "/opt/homebrew/opt/katago/share/katago"


def _resolve_share():
    if os.path.isdir(_BREW_SHARE):
        return _BREW_SHARE
    try:
        prefix = subprocess.check_output(
            ["brew", "--prefix", "katago"], text=True, timeout=10
        ).strip()
        cand = os.path.join(prefix, "share", "katago")
        if os.path.isdir(cand):
            return cand
    except Exception:
        pass
    return _BREW_SHARE


_SHARE = _resolve_share()

KATAGO_BIN = os.environ.get("KATAGO_BIN") or shutil.which("katago") or "katago"
KATAGO_MODEL = os.environ.get("KATAGO_MODEL") or os.path.join(
    _SHARE, "kata1-b18c384nbt-s9996604416-d4316597426.bin.gz"
)
KATAGO_CONFIG = os.environ.get("KATAGO_CONFIG") or os.path.join(
    _SHARE, "configs", "analysis_example.cfg"
)
KATAGO_LOG = os.environ.get("KATAGO_LOG") or "/tmp/katago_engine.log"


class KataGoError(RuntimeError):
    pass


class KataGoEngine:
    """Persistent KataGo analysis-engine subprocess shared across games."""

    def __init__(self):
        self.proc = None
        self._pending = {}  # query id -> asyncio.Future
        self._counter = 0
        self._reader_task = None
        self._log = None

    async def start(self):
        for path, label in ((KATAGO_MODEL, "model"), (KATAGO_CONFIG, "config")):
            if not os.path.isfile(path):
                raise KataGoError(f"KataGo {label} not found: {path}")

        self._log = open(KATAGO_LOG, "w")
        self.proc = await asyncio.create_subprocess_exec(
            KATAGO_BIN, "analysis",
            "-config", KATAGO_CONFIG,
            "-model", KATAGO_MODEL,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=self._log,
        )
        self._reader_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self):
        assert self.proc and self.proc.stdout
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            fut = self._pending.pop(msg.get("id"), None)
            if fut and not fut.done():
                fut.set_result(msg)
        # process died: fail everything still waiting
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(KataGoError("KataGo engine stopped"))
        self._pending.clear()

    async def analyze(self, moves, board_size, komi, rules, max_visits):
        """moves: list of [color, gtp] pairs. Returns the parsed JSON response."""
        if self.proc is None or self.proc.returncode is not None:
            raise KataGoError("KataGo engine is not running")

        self._counter += 1
        qid = f"q{self._counter}"
        request = {
            "id": qid,
            "moves": moves,
            "rules": rules,
            "komi": komi,
            "boardXSize": board_size,
            "boardYSize": board_size,
            "maxVisits": max_visits,
        }
        fut = asyncio.get_running_loop().create_future()
        self._pending[qid] = fut

        self.proc.stdin.write((json.dumps(request) + "\n").encode())
        await self.proc.stdin.drain()

        try:
            msg = await asyncio.wait_for(fut, timeout=120)
        except asyncio.TimeoutError:
            self._pending.pop(qid, None)
            raise KataGoError("KataGo analysis timed out")

        if "error" in msg:
            raise KataGoError(f"KataGo: {msg['error']}")
        return msg

    async def stop(self):
        if self.proc and self.proc.returncode is None:
            try:
                self.proc.stdin.close()
                self.proc.terminate()
                await asyncio.wait_for(self.proc.wait(), timeout=5)
            except Exception:
                self.proc.kill()
        if self._log:
            self._log.close()
