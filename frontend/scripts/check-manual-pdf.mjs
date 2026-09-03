import { readFile, stat } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const config = JSON.parse(await readFile(path.join(frontendRoot, 'src/config/manual.json'), 'utf8'))
const pdfPath = path.join(frontendRoot, 'public', config.url.replace(/^\//, ''))
const details = await stat(pdfPath)
const header = Buffer.alloc(5)
const file = await import('node:fs/promises').then(({ open }) => open(pdfPath, 'r'))
try {
  await file.read(header, 0, header.length, 0)
} finally {
  await file.close()
}

if (!details.isFile() || details.size < 50_000 || header.toString() !== '%PDF-') {
  throw new Error(`Manual PDF is missing or invalid: ${pdfPath}`)
}

console.log(`Manual PDF verified: ${config.url} (${details.size} bytes)`)
