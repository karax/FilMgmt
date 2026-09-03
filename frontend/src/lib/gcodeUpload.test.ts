import { describe, expect, it } from 'vitest'

import {
  formatFileSize,
  validateGCodeFile,
} from './gcodeUpload'

describe('G-code file validation', () => {
  it('accepts lowercase and uppercase G-code extensions', () => {
    expect(validateGCodeFile(new File(['G1'], 'benchy.gcode'))).toBeNull()
    expect(validateGCodeFile(new File(['G1'], 'BENCHY.GCODE'))).toBeNull()
  })

  it.each(['model.stl', 'model.3mf', 'model.txt', 'model'])('rejects %s', (name) => {
    expect(validateGCodeFile(new File(['data'], name))).toBe('invalidExtension')
  })

  it('rejects empty files', () => {
    expect(validateGCodeFile(new File([], 'empty.gcode'))).toBe('emptyFile')
  })

  it('accepts the exact limit and rejects one byte above it', () => {
    const exact = new File(['1234'], 'exact.gcode')
    const over = new File(['12345'], 'over.gcode')

    expect(validateGCodeFile(exact, 4)).toBeNull()
    expect(validateGCodeFile(over, 4)).toBe('tooLarge')
  })

  it('formats file sizes without reading file contents', () => {
    expect(formatFileSize(800, 'en')).toBe('800 B')
    expect(formatFileSize(3.8 * 1024 * 1024, 'en')).toBe('3.8 MB')
  })
})
