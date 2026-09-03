const SPOOL_CODE_PATTERN = /^FIL-[0-9]{4,}$/
const SVG_NAMESPACE = 'http://www.w3.org/2000/svg'

export type SpoolQrSvgFile = {
  contents: string
  filename: string
  payload: string
}

export function isValidSpoolCode(code: unknown): code is string {
  return typeof code === 'string' && SPOOL_CODE_PATTERN.test(code)
}

export function buildSpoolQrPayload(code: unknown): string | null {
  return isValidSpoolCode(code) ? `fcc:spool:${code}` : null
}

export function parseSpoolQrPayload(value: unknown): string | null {
  if (typeof value !== 'string') return null

  const payload = value.trim()
  const prefix = 'fcc:spool:'
  if (!payload.startsWith(prefix)) return null

  const code = payload.slice(prefix.length)
  return isValidSpoolCode(code) ? code : null
}

export function buildSpoolQrLandingPath(code: unknown): string | null {
  return isValidSpoolCode(code) ? `/qr/spool/${encodeURIComponent(code)}` : null
}

export function buildSpoolQrSvgFile(
  qrElement: SVGSVGElement,
  code: unknown,
): SpoolQrSvgFile | null {
  const payload = buildSpoolQrPayload(code)
  if (!payload || typeof code !== 'string') return null

  const svg = qrElement.cloneNode(true) as SVGSVGElement
  const viewBox = parseViewBox(svg.getAttribute('viewBox'))
  if (!viewBox) return null

  const [minX, minY, width, height] = viewBox
  const labelHeight = Math.max(8, height * 0.22)
  const exportedHeight = height + labelHeight
  const labelBackground = document.createElementNS(SVG_NAMESPACE, 'rect')
  labelBackground.setAttribute('x', String(minX))
  labelBackground.setAttribute('y', String(minY + height))
  labelBackground.setAttribute('width', String(width))
  labelBackground.setAttribute('height', String(labelHeight))
  labelBackground.setAttribute('fill', '#ffffff')

  const label = document.createElementNS(SVG_NAMESPACE, 'text')
  label.setAttribute('x', String(minX + width / 2))
  label.setAttribute('y', String(minY + height + labelHeight / 2))
  label.setAttribute('fill', '#000000')
  label.setAttribute('font-family', 'ui-monospace, SFMono-Regular, Consolas, monospace')
  label.setAttribute('font-size', String(Math.max(2, height * 0.065)))
  label.setAttribute('font-weight', '700')
  label.setAttribute('text-anchor', 'middle')
  label.setAttribute('dominant-baseline', 'middle')
  label.textContent = code

  svg.append(labelBackground, label)
  svg.setAttribute('xmlns', SVG_NAMESPACE)
  svg.setAttribute('viewBox', `${minX} ${minY} ${width} ${exportedHeight}`)
  svg.setAttribute('width', '256')
  svg.setAttribute('height', String(Math.round(256 * exportedHeight / width)))
  svg.setAttribute('data-qr-payload', payload)
  svg.setAttribute('style', 'background:#ffffff;color-scheme:light')
  svg.removeAttribute('class')

  return {
    contents: `<?xml version="1.0" encoding="UTF-8"?>\n${new XMLSerializer().serializeToString(svg)}`,
    filename: `${code}-qr.svg`,
    payload,
  }
}

export function downloadSpoolQrSvg(qrElement: SVGSVGElement, code: unknown): boolean {
  const file = buildSpoolQrSvgFile(qrElement, code)
  if (!file) return false

  const url = URL.createObjectURL(new Blob([file.contents], { type: 'image/svg+xml;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = file.filename
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
  return true
}

function parseViewBox(value: string | null): [number, number, number, number] | null {
  if (!value) return null
  const values = value.trim().split(/[ ,]+/).map(Number)
  if (values.length !== 4 || values.some((part) => !Number.isFinite(part))) return null
  const [minX, minY, width, height] = values
  if (width <= 0 || height <= 0) return null
  return [minX, minY, width, height]
}
