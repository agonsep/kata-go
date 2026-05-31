import { useEffect, useState } from 'react'
import Goban from './Goban'
import { api } from './api'
import './App.css'

const emptyBoard = (size) =>
  Array.from({ length: size }, () => Array(size).fill(0))

const LEVELS = [
  ['easy', 'Easy'],
  ['medium', 'Medium'],
  ['hard', 'Hard'],
  ['max', 'Max'],
]

export default function App() {
  const [game, setGame] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [hint, setHint] = useState(null)
  // null => follow the live position; a number => reviewing that snapshot
  const [reviewIndex, setReviewIndex] = useState(null)
  const [form, setForm] = useState({
    boardSize: 9,
    humanColor: 'black',
    aiLevel: 'medium',
  })

  const size = game ? game.boardSize : form.boardSize
  const history = game?.history || []
  const liveIndex = history.length - 1
  const viewIndex =
    reviewIndex == null ? liveIndex : Math.min(reviewIndex, liveIndex)
  const atLive = viewIndex >= liveIndex
  const snap = history.length ? history[viewIndex] : null

  const board = snap ? snap.board : game ? game.board : emptyBoard(size)
  const displayedLast = snap ? snap.lastMove : game?.lastMove
  const humanTurn =
    game && game.status === 'playing' && game.currentPlayer === game.humanColor
  const playing = game && game.status === 'playing'
  const canPlay = humanTurn && atLive
  // undo needs at least one of the human's own moves to roll back
  const canUndo =
    game && game.moveCount >= (game.humanColor === 'black' ? 1 : 2)

  // Arrow keys scrub through the game.
  useEffect(() => {
    if (!game) return
    const onKey = (e) => {
      if (e.key === 'ArrowLeft') {
        e.preventDefault()
        setReviewIndex((i) => Math.max(0, (i == null ? liveIndex : i) - 1))
      } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        setReviewIndex((i) => {
          const n = (i == null ? liveIndex : i) + 1
          return n >= liveIndex ? null : n
        })
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [game, liveIndex])

  async function run(fn) {
    setBusy(true)
    setError('')
    try {
      const next = await fn()
      if (next) setGame(next)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const startGame = () => run(async () => {
    setHint(null)
    setReviewIndex(null)
    return api.newGame(form)
  })

  const play = (x, y) => run(async () => {
    setHint(null)
    setReviewIndex(null)
    return api.move(game.id, x, y)
  })

  const doPass = () => run(() => { setReviewIndex(null); return api.pass(game.id) })
  const doResign = () => run(() => api.resign(game.id))
  const doUndo = () => run(() => {
    setHint(null)
    setReviewIndex(null)
    return api.undo(game.id)
  })

  const goFirst = () => setReviewIndex(0)
  const goPrev = () =>
    setReviewIndex((i) => Math.max(0, (i == null ? liveIndex : i) - 1))
  const goNext = () =>
    setReviewIndex((i) => {
      const n = (i == null ? liveIndex : i) + 1
      return n >= liveIndex ? null : n
    })
  const goLive = () => setReviewIndex(null)

  const getHint = () => run(async () => {
    const h = await api.hint(game.id)
    if (h.isPass) {
      setError('KataGo suggests passing.')
    } else {
      setHint({ x: h.x, y: h.y })
    }
    return null
  })

  const winrate = game?.blackWinrate
  const score = game?.blackScoreLead

  return (
    <div className="app">
      <h1>Play Go vs KataGo</h1>

      <div className="layout">
        <div className="boardcol">
          <Goban
            board={board}
            size={size}
            lastMove={displayedLast}
            hint={atLive ? hint : null}
            humanColor={game?.humanColor || form.humanColor}
            disabled={busy || !canPlay}
            onPlay={play}
          />

          {game && (
            <div className={`nav ${atLive ? '' : 'reviewing'}`}>
              <button onClick={goFirst} disabled={viewIndex <= 0} title="Start">⏮</button>
              <button onClick={goPrev} disabled={viewIndex <= 0} title="Previous (←)">◀</button>
              <span className="navlabel">
                {atLive ? 'Move' : 'Reviewing'} {snap?.moveNumber ?? 0} / {history[liveIndex]?.moveNumber ?? 0}
              </span>
              <button onClick={goNext} disabled={atLive} title="Next (→)">▶</button>
              <button className="live" onClick={goLive} disabled={atLive} title="Back to current">⏭ Current</button>
            </div>
          )}
        </div>

        <aside className="panel">
          {game && (
            <div className="card status">
              {game.status === 'finished' ? (
                <div className="result">{game.result}</div>
              ) : busy ? (
                <div className="turn thinking">KataGo is thinking…</div>
              ) : (
                <div className="turn">
                  {humanTurn ? 'Your move' : 'KataGo to move'}
                  <span className={`dot ${game.currentPlayer}`} />
                </div>
              )}

              <div className="winbar" title="Black win probability">
                <div
                  className="winbar-black"
                  style={{ width: `${(winrate ?? 0.5) * 100}%` }}
                />
              </div>
              <div className="winrow">
                <span>Black {winrate == null ? '—' : `${Math.round(winrate * 100)}%`}</span>
                <span>
                  {score == null
                    ? ''
                    : score >= 0
                      ? `B+${score.toFixed(1)}`
                      : `W+${(-score).toFixed(1)}`}
                </span>
              </div>

              <dl className="meta">
                <div><dt>You</dt><dd>{game.humanColor}</dd></div>
                <div><dt>Move</dt><dd>{game.moveCount}</dd></div>
                <div><dt>Captures B/W</dt><dd>{game.captures.black} / {game.captures.white}</dd></div>
                <div><dt>Komi</dt><dd>{game.komi}</dd></div>
              </dl>
            </div>
          )}

          {game && (
            <div className="card controls">
              <button onClick={doUndo} disabled={busy || !canUndo}>Undo</button>
              <button onClick={doPass} disabled={busy || !canPlay}>Pass</button>
              <button onClick={getHint} disabled={busy || !canPlay}>Hint</button>
              <button className="danger" onClick={doResign} disabled={busy || !playing}>Resign</button>
            </div>
          )}

          <div className="card setup">
            <h2>New game</h2>
            <label>Board size</label>
            <div className="choices">
              {[9, 13, 19].map((s) => (
                <button
                  key={s}
                  className={form.boardSize === s ? 'sel' : ''}
                  onClick={() => setForm({ ...form, boardSize: s })}
                >{s}×{s}</button>
              ))}
            </div>
            <label>Your color</label>
            <div className="choices">
              {['black', 'white'].map((c) => (
                <button
                  key={c}
                  className={form.humanColor === c ? 'sel' : ''}
                  onClick={() => setForm({ ...form, humanColor: c })}
                >{c}</button>
              ))}
            </div>
            <label>KataGo strength</label>
            <div className="choices">
              {LEVELS.map(([v, label]) => (
                <button
                  key={v}
                  className={form.aiLevel === v ? 'sel' : ''}
                  onClick={() => setForm({ ...form, aiLevel: v })}
                >{label}</button>
              ))}
            </div>
            <button className="primary" onClick={startGame} disabled={busy}>
              Start game
            </button>
          </div>

          {error && <div className="card error">{error}</div>}
        </aside>
      </div>
    </div>
  )
}
