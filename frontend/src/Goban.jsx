import { useEffect, useRef, useState } from 'react'

const DIM = 560
const STAR_POINTS = {
  9: [[2, 2], [6, 2], [4, 4], [2, 6], [6, 6]],
  13: [[3, 3], [9, 3], [6, 6], [3, 9], [9, 9]],
  19: [[3, 3], [9, 3], [15, 3], [3, 9], [9, 9], [15, 9], [3, 15], [9, 15], [15, 15]],
}

export default function Goban({ board, size, lastMove, hint, humanColor, disabled, onPlay }) {
  const canvasRef = useRef(null)
  const [hover, setHover] = useState(null)

  const pad = DIM / (size + 1)
  const step = (DIM - 2 * pad) / (size - 1)
  const toPx = (i) => pad + i * step

  useEffect(() => {
    const canvas = canvasRef.current
    const dpr = window.devicePixelRatio || 1
    canvas.width = DIM * dpr
    canvas.height = DIM * dpr
    const ctx = canvas.getContext('2d')
    ctx.scale(dpr, dpr)

    // board background
    ctx.fillStyle = '#e3b25b'
    ctx.fillRect(0, 0, DIM, DIM)

    // grid
    ctx.strokeStyle = '#4a3618'
    ctx.lineWidth = 1
    for (let i = 0; i < size; i++) {
      ctx.beginPath()
      ctx.moveTo(toPx(i), toPx(0))
      ctx.lineTo(toPx(i), toPx(size - 1))
      ctx.moveTo(toPx(0), toPx(i))
      ctx.lineTo(toPx(size - 1), toPx(i))
      ctx.stroke()
    }

    // star points
    ctx.fillStyle = '#4a3618'
    for (const [sx, sy] of STAR_POINTS[size] || []) {
      ctx.beginPath()
      ctx.arc(toPx(sx), toPx(sy), 3, 0, 2 * Math.PI)
      ctx.fill()
    }

    const r = step * 0.46
    const drawStone = (x, y, color, alpha = 1) => {
      const cx = toPx(x)
      const cy = toPx(y)
      ctx.globalAlpha = alpha
      const grad = ctx.createRadialGradient(
        cx - r * 0.35, cy - r * 0.35, r * 0.15, cx, cy, r,
      )
      if (color === 1) {
        grad.addColorStop(0, '#6a6a6a')
        grad.addColorStop(1, '#0a0a0a')
      } else {
        grad.addColorStop(0, '#ffffff')
        grad.addColorStop(1, '#c4c4c4')
      }
      ctx.fillStyle = grad
      ctx.beginPath()
      ctx.arc(cx, cy, r, 0, 2 * Math.PI)
      ctx.fill()
      ctx.globalAlpha = 1
    }

    // stones
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        if (board[y][x]) drawStone(x, y, board[y][x])
      }
    }

    // last-move marker
    if (lastMove && lastMove.x !== undefined) {
      const owner = board[lastMove.y][lastMove.x]
      ctx.strokeStyle = owner === 1 ? '#ffffff' : '#000000'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.arc(toPx(lastMove.x), toPx(lastMove.y), r * 0.45, 0, 2 * Math.PI)
      ctx.stroke()
    }

    // hint marker
    if (hint && hint.x !== undefined) {
      ctx.strokeStyle = '#1769ff'
      ctx.lineWidth = 3
      ctx.beginPath()
      ctx.arc(toPx(hint.x), toPx(hint.y), r * 0.85, 0, 2 * Math.PI)
      ctx.stroke()
    }

    // hover preview
    if (hover && !disabled && !board[hover.y][hover.x]) {
      drawStone(hover.x, hover.y, humanColor === 'black' ? 1 : 2, 0.4)
    }
  }, [board, size, lastMove, hint, hover, disabled, humanColor])

  const locate = (e) => {
    const rect = canvasRef.current.getBoundingClientRect()
    const px = ((e.clientX - rect.left) / rect.width) * DIM
    const py = ((e.clientY - rect.top) / rect.height) * DIM
    const x = Math.round((px - pad) / step)
    const y = Math.round((py - pad) / step)
    if (x < 0 || x >= size || y < 0 || y >= size) return null
    if (Math.hypot(px - toPx(x), py - toPx(y)) > step * 0.5) return null
    return { x, y }
  }

  return (
    <canvas
      ref={canvasRef}
      className="goban"
      style={{ width: DIM, height: DIM, cursor: disabled ? 'default' : 'pointer' }}
      onMouseMove={(e) => setHover(locate(e))}
      onMouseLeave={() => setHover(null)}
      onClick={(e) => {
        if (disabled) return
        const p = locate(e)
        if (p && !board[p.y][p.x]) onPlay(p.x, p.y)
      }}
    />
  )
}
