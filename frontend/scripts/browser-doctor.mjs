import {
  architecture,
  checkHttp,
  chromiumVersion,
  findChromiumExecutable,
  playwrightVersion,
} from './browser-support.mjs'

let chromium = null
let chromiumFailure = null

try {
  chromium = findChromiumExecutable()
} catch (error) {
  chromiumFailure = error instanceof Error ? error.message : String(error)
}

const frontendUrl = process.env.FCC_DOCTOR_FRONTEND_URL || 'http://127.0.0.1:5173/'
const backendUrl = process.env.FCC_DOCTOR_BACKEND_URL || 'http://127.0.0.1:8000/api/health'
const [frontend, backend] = await Promise.all([
  checkHttp(frontendUrl),
  checkHttp(backendUrl),
])

console.log(`Architecture: ${architecture()} (${process.arch})`)
console.log(`Node: ${process.version}`)
console.log(`Playwright: ${playwrightVersion()}`)
console.log(chromium ? `Chromium: FOUND (${chromium})` : `Chromium: MISSING (${chromiumFailure})`)
if (chromium) console.log(`Chromium version: ${chromiumVersion(chromium)}`)
console.log(`Frontend (${frontendUrl}): ${frontend.ok ? `REACHABLE (${frontend.status})` : `UNAVAILABLE (${frontend.error ?? frontend.status})`}`)
console.log(`Backend (${backendUrl}): ${backend.ok ? `REACHABLE (${backend.status})` : `UNAVAILABLE (${backend.error ?? backend.status})`}`)

if (!chromium) process.exitCode = 2
else if (!frontend.ok && !backend.ok) process.exitCode = 5
else if (!frontend.ok) process.exitCode = 3
else if (!backend.ok) process.exitCode = 4
