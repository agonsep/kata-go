async function request(path, options) {
  const res = await fetch(`/api${path}`, {
    headers: { 'content-type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail || detail
    } catch {
      // response had no JSON body
    }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  newGame: (config) =>
    request('/games', { method: 'POST', body: JSON.stringify(config) }),
  move: (id, x, y) =>
    request(`/games/${id}/move`, {
      method: 'POST',
      body: JSON.stringify({ x, y }),
    }),
  pass: (id) => request(`/games/${id}/pass`, { method: 'POST' }),
  resign: (id) => request(`/games/${id}/resign`, { method: 'POST' }),
  hint: (id) => request(`/games/${id}/hint`, { method: 'POST' }),
}
