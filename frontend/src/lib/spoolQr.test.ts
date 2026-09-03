import { describe, expect, it } from 'vitest'

import {
  buildSpoolQrLandingPath,
  buildSpoolQrPayload,
  buildSpoolQrSvgFile,
  parseSpoolQrPayload,
} from './spoolQr'

describe('spool QR helpers', () => {
  it.each([
    ['FIL-0001', 'fcc:spool:FIL-0001'],
    ['FIL-0123', 'fcc:spool:FIL-0123'],
  ])('builds the canonical payload for %s', (code, payload) => {
    expect(buildSpoolQrPayload(code)).toBe(payload)
  })

  it.each([undefined, null, '', 'FIL-123', 'FIL-ABCD', ' FIL-0001 '])(
    'does not build a payload for invalid code %s',
    (code) => expect(buildSpoolQrPayload(code)).toBeNull(),
  )

  it('never includes the current origin or a network address', () => {
    const payload = buildSpoolQrPayload('FIL-0007')
    expect(payload).toBe('fcc:spool:FIL-0007')
    expect(payload).not.toContain(window.location.origin)
    expect(payload).not.toContain('localhost')
    expect(payload).not.toContain('192.168.')
    expect(payload).not.toContain('100.')
  })

  it('parses the canonical payload into its spool code', () => {
    expect(parseSpoolQrPayload('fcc:spool:FIL-0007')).toBe('FIL-0007')
  })

  it('ignores external whitespace when parsing', () => {
    expect(parseSpoolQrPayload('  fcc:spool:FIL-0007  ')).toBe('FIL-0007')
  })

  it.each([
    '',
    'FIL-0007',
    'spool:FIL-0007',
    'fcc:material:FIL-0007',
    'http://example.com',
    'fcc:spool:',
    'fcc:spool:undefined',
    undefined,
    null,
  ])('rejects a non-canonical QR value: %s', (value) => {
    expect(parseSpoolQrPayload(value)).toBeNull()
  })

  it('builds the internal landing path from the public spool code', () => {
    expect(buildSpoolQrLandingPath('FIL-0007')).toBe('/qr/spool/FIL-0007')
  })

  it('builds a printable SVG file with the canonical payload and predictable filename', () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.setAttribute('viewBox', '0 0 29 29')
    svg.innerHTML = '<rect width="29" height="29" fill="#ffffff"/><path d="M4 4h1v1H4z" fill="#000000"/>'

    const file = buildSpoolQrSvgFile(svg, 'FIL-0007')

    expect(file).not.toBeNull()
    expect(file?.filename).toBe('FIL-0007-qr.svg')
    expect(file?.payload).toBe('fcc:spool:FIL-0007')
    expect(file?.contents).toContain('data-qr-payload="fcc:spool:FIL-0007"')
    expect(file?.contents).toContain('<path')
    expect(file?.contents).toContain('FIL-0007</text>')
    expect(file?.contents).toContain('#ffffff')
    expect(file?.contents).toContain('#000000')
  })
})
