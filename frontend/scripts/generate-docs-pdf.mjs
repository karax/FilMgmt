import { mkdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { marked } from 'marked'
import { chromium } from 'playwright'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const projectRoot = path.resolve(frontendRoot, '..')
const configPath = path.join(frontendRoot, 'src/config/manual.json')
const config = JSON.parse(await readFile(configPath, 'utf8'))
const sourcePath = path.resolve(projectRoot, config.source)
const outputPath = path.join(frontendRoot, 'public', config.url.replace(/^\//, ''))
const manualCss = await readFile(path.join(path.dirname(sourcePath), 'manual.css'), 'utf8')
const packageInfo = JSON.parse(await readFile(path.join(frontendRoot, 'package.json'), 'utf8'))
const generatedDate = new Intl.DateTimeFormat('pt-BR', {
  day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Europe/Lisbon',
}).format(new Date())

if (path.basename(config.url) !== config.filename) {
  throw new Error('Manual URL and download filename must identify the same file.')
}

const source = await readFile(sourcePath, 'utf8')
const titleMatch = /^#\s+(.+)\n\n##\s+(.+)\n/.exec(source)
if (!titleMatch) throw new Error('The manual must begin with a title and subtitle.')

const title = titleMatch[1]
const subtitle = titleMatch[2]
const markdownBody = source.slice(titleMatch[0].length)
const markdownWithImages = await embedImages(markdownBody, path.dirname(sourcePath))
let content = await marked.parse(markdownWithImages, { gfm: true })

const headings = [...markdownBody.matchAll(/^##\s+(.+)$/gm)].map((match) => match[1])
let headingIndex = 0
content = content.replace(/<h2>([\s\S]*?)<\/h2>/g, (_, inner) => {
  const text = headings[headingIndex++] ?? inner.replace(/<[^>]+>/g, '')
  return `<h2 id="${slug(text)}">${inner}</h2>`
})
content = content.replace(
  /<p>(<img[^>]+>)<\/p>\s*<p><em>([\s\S]*?)<\/em><\/p>/g,
  '<figure>$1<figcaption>$2</figcaption></figure>',
)

const tableOfContents = headings.map((heading) => `<li><a href="#${slug(heading)}">${escapeHtml(heading)}</a></li>`).join('')
const html = `<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)} — Filament Command Center</title>
  <style>
    @page { size: A4; margin: 18mm 17mm 20mm; }
    :root { color-scheme: light; }
    * { box-sizing: border-box; }
    html { font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #172126; background: #fff; }
    body { margin: 0; font-size: 10.5pt; line-height: 1.55; }
    .cover { min-height: 235mm; display: flex; flex-direction: column; justify-content: center; padding: 15mm 4mm; break-after: page; }
    .product { color: #008e95; font-size: 9pt; font-weight: 800; letter-spacing: .22em; text-transform: uppercase; }
    .cover h1 { margin: 8mm 0 3mm; font-size: 34pt; line-height: 1.05; letter-spacing: -.035em; color: #10191d; }
    .cover .subtitle { max-width: 135mm; margin: 0; font-size: 18pt; line-height: 1.35; color: #53646c; }
    .cover .rule { width: 28mm; height: 1.5mm; margin: 13mm 0 8mm; background: #00a9af; }
    .cover .edition { color: #667880; font-size: 10pt; }
    .contents { break-after: page; padding-top: 6mm; }
    .contents ol { columns: 2; column-gap: 12mm; padding-left: 6mm; }
    .contents li { break-inside: avoid; margin: 0 0 3mm; padding-right: 4mm; }
    .contents a { color: #26383f; text-decoration: none; }
    main > p:first-child { font-size: 12pt; color: #53646c; }
    h2, h3 { break-after: avoid; color: #152126; }
    h2 { margin: 10mm 0 4mm; padding-bottom: 2.5mm; border-bottom: .4mm solid #cbd7da; font-size: 19pt; line-height: 1.2; letter-spacing: -.018em; }
    h3 { margin: 7mm 0 2.5mm; font-size: 13pt; }
    p { margin: 0 0 4mm; }
    a { color: #007f86; text-decoration: underline; text-underline-offset: 1.5pt; }
    strong { color: #122126; }
    ul, ol { margin: 0 0 5mm; padding-left: 7mm; }
    li { margin-bottom: 1.5mm; }
    blockquote { break-inside: avoid; margin: 5mm 0; padding: 4mm 5mm; border-left: 1.2mm solid #00a9af; border-radius: 1.5mm; background: #eef8f8; color: #273b42; }
    blockquote > :last-child { margin-bottom: 0; }
    pre { break-inside: avoid; margin: 5mm 0; padding: 4mm 5mm; overflow-wrap: anywhere; border-radius: 2mm; background: #111d22; color: #e9f2f3; font: 9pt/1.5 ui-monospace, SFMono-Regular, Consolas, monospace; white-space: pre-wrap; }
    code { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .92em; }
    :not(pre) > code { padding: .3mm 1mm; border-radius: 1mm; background: #edf2f3; color: #18353c; }
    table { width: 100%; margin: 5mm 0 6mm; border-collapse: collapse; break-inside: avoid; font-size: 9.3pt; }
    th { background: #e7f1f2; color: #1d343b; text-align: left; }
    th, td { padding: 2.5mm 3mm; border: .3mm solid #cbd7da; vertical-align: top; }
    tbody tr:nth-child(even) { background: #f7f9f9; }
    figure { margin: 6mm 0 7mm; break-inside: avoid; text-align: center; }
    figure img { display: block; max-width: 100%; max-height: 170mm; width: auto; height: auto; margin: 0 auto; border: .3mm solid #c8d3d6; border-radius: 2mm; }
    figure figcaption { margin-top: 2.5mm; color: #64747b; font-size: 8.8pt; font-style: italic; }
    hr { margin: 8mm 0; border: 0; border-top: .4mm solid #cbd7da; }
    ${manualCss}
  </style>
</head>
<body>
  <section class="cover">
    <div class="product">Filament Command Center</div>
    <h1>${escapeHtml(title)}</h1>
    <p class="subtitle">${escapeHtml(subtitle)}</p>
    <div class="rule"></div>
    <p class="edition">Versão do produto ${escapeHtml(packageInfo.version)} · Atualizado em ${escapeHtml(generatedDate)}</p>
  </section>
  <nav class="contents" aria-label="Sumário">
    <div class="product">Navegação do manual</div>
    <h2>Sumário</h2>
    <ol>${tableOfContents}</ol>
  </nav>
  <main>${content}</main>
</body>
</html>`

await mkdir(path.dirname(outputPath), { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium' })
try {
  const page = await browser.newPage()
  await page.setContent(html, { waitUntil: 'load' })
  await page.evaluate(async () => {
    await document.fonts.ready
    await Promise.all([...document.images].map((image) => image.complete ? undefined : new Promise((resolve, reject) => {
      image.addEventListener('load', resolve, { once: true })
      image.addEventListener('error', reject, { once: true })
    })))
  })
  await page.emulateMedia({ media: 'print' })
  await page.pdf({
    path: outputPath,
    format: 'A4',
    preferCSSPageSize: true,
    printBackground: true,
    tagged: true,
    outline: true,
    displayHeaderFooter: true,
    headerTemplate: '<div style="width:100%;padding:0 17mm;font:8px system-ui;color:#7a898f;letter-spacing:.08em;text-transform:uppercase">Filament Command Center — Manual do Usuário</div>',
    footerTemplate: `<div style="width:100%;padding:0 17mm;display:flex;justify-content:space-between;font:8px system-ui;color:#7a898f"><span>Atualizado em ${escapeHtml(generatedDate)}</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`,
  })
} finally {
  await browser.close()
}

const pdf = await readFile(outputPath)
if (pdf.length < 50_000 || pdf.subarray(0, 5).toString() !== '%PDF-') {
  throw new Error('Generated manual is not a valid non-empty PDF.')
}

console.log(`Generated ${path.relative(projectRoot, outputPath)} (${pdf.length} bytes)`)

async function embedImages(markdown, sourceDirectory) {
  let result = markdown
  const paths = [...markdown.matchAll(/!\[[^\]]*\]\(([^)\s]+)\)/g)].map((match) => match[1])
  for (const imagePath of new Set(paths)) {
    if (/^(?:data:|https?:)/.test(imagePath)) continue
    const absolutePath = path.resolve(sourceDirectory, imagePath)
    const encoded = (await readFile(absolutePath)).toString('base64')
    const extension = path.extname(absolutePath).slice(1).toLowerCase()
    const mime = extension === 'jpg' || extension === 'jpeg' ? 'image/jpeg' : 'image/png'
    result = result.replaceAll(`(${imagePath})`, `(data:${mime};base64,${encoded})`)
  }
  return result
}

function slug(value) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

function escapeHtml(value) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;')
}
