import { mkdtemp, rm } from 'node:fs/promises'
import { spawn, spawnSync } from 'node:child_process'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Dedicated test server: never opens the application's normal database.
const backend = fileURLToPath(new URL('../../backend/', import.meta.url))
const directory = await mkdtemp(path.join(os.tmpdir(), 'fcc-wave2-'))
const python = process.env.FCC_TEST_PYTHON || path.join(backend, '.venv/bin/python')
const env = { ...process.env, DATABASE_URL: `sqlite+pysqlite:///${directory}/test.sqlite`, GCODE_UPLOAD_DIRECTORY: path.join(directory, 'uploads') }
const migration = spawnSync(python, ['-m', 'alembic', 'upgrade', 'head'], { cwd: backend, env, stdio: 'inherit' })
if (migration.status !== 0) throw new Error('Isolated Wave 2 database migration failed.')
if (process.env.FCC_WAVE2_SEED_CATALOGS === '1') {
  for (const module of ['app.scripts.seed_manufacturers', 'app.scripts.seed_materials']) {
    const seed = spawnSync(python, ['-m', module], { cwd: backend, env, stdio: 'inherit' })
    if (seed.status !== 0) throw new Error(`Isolated catalog seed failed: ${module}`)
  }
}
const server = spawn(python, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '18002'], { cwd: backend, env, stdio: 'inherit' })
process.on('SIGTERM', () => server.kill('SIGTERM'))
process.on('SIGINT', () => server.kill('SIGTERM'))
server.on('exit', async code => { await rm(directory, { recursive: true, force: true }); process.exit(code ?? 0) })
