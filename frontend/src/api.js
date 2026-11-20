const BASE = '/api'
export const getToken = () => localStorage.getItem('askue_token') || ''
export const setToken = (t) => (t ? localStorage.setItem('askue_token', t) : localStorage.removeItem('askue_token'))

async function request(path, { method = 'GET', body, form, signal } = {}) {
  const headers = {}
  const t = getToken()
  if (t) headers.Authorization = `Bearer ${t}`
  let payload
  if (form) payload = form
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  let res
  try {
    res = await fetch(BASE + path, { method, headers, body: payload, signal })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new Error("Serverga ulanib bo'lmadi")
  }
  if (res.status === 401 && path !== '/auth/login') {
    window.dispatchEvent(new Event('askue-logout'))
  }
  if (!res.ok) {
    let msg = `Xatolik (${res.status})`
    try { const j = await res.json(); if (j.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail) } catch { /* */ }
    throw new Error(msg)
  }
  return res
}

const json = async (p, o) => (await request(p, o)).json()
export const api = {
  get: (p, signal) => json(p, { signal }),
  post: (p, body) => json(p, { method: 'POST', body }),
  patch: (p, body) => json(p, { method: 'PATCH', body }),
  put: (p, body) => json(p, { method: 'PUT', body }),
  del: (p) => json(p, { method: 'DELETE' }),
}

export async function download(path, filename) {
  const res = await request(path)
  const blob = await res.blob()
  const cd = res.headers.get('content-disposition') || ''
  const m2 = cd.match(/filename\*=UTF-8''([^;]+)/i)
  const m = m2 ? [null, decodeURIComponent(m2[1])] : cd.match(/filename="([^"]+)"/)
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = m ? m[1] : filename
  document.body.appendChild(a)
  a.click()
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove() }, 500)
}

// Faylni yangi oynada ochish (PDF ko'rish) — token bilan olinadi
export async function openFile(path) {
  const w = window.open('', '_blank')
  try {
    const res = await request(path)
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    if (w) w.location.href = url
    else window.location.href = url
    setTimeout(() => URL.revokeObjectURL(url), 5 * 60 * 1000)
  } catch (e) { w?.close(); throw e }
}

// Fayl yuklash (jarayon foizi bilan)
export function uploadForm(path, form, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', BASE + path)
    const t = getToken()
    if (t) xhr.setRequestHeader('Authorization', `Bearer ${t}`)
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total)
    xhr.onload = () => {
      let j = {}
      try { j = JSON.parse(xhr.responseText) } catch { /* */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(j)
      else reject(new Error(j.detail || `Xatolik (${xhr.status})`))
    }
    xhr.onerror = () => reject(new Error("Serverga ulanib bo'lmadi"))
    xhr.send(form)
  })
}

export const qs = (o) => {
  const p = new URLSearchParams()
  Object.entries(o).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') p.set(k, v) })
  const s = p.toString()
  return s ? `?${s}` : ''
}
