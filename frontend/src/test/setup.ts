import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { createElement } from 'react'
import { afterEach, vi } from 'vitest'
import i18n, { LANGUAGE_STORAGE_KEY } from '../i18n'

vi.mock('react-chartjs-2', () => ({
  Bar: ({ 'aria-label': ariaLabel }: { 'aria-label'?: string }) => createElement('div', { 'aria-label': ariaLabel, 'data-chart': 'bar', role: 'img' }),
  Doughnut: ({ 'aria-label': ariaLabel }: { 'aria-label'?: string }) => createElement('div', { 'aria-label': ariaLabel, 'data-chart': 'doughnut', role: 'img' }),
  Line: ({ 'aria-label': ariaLabel }: { 'aria-label'?: string }) => createElement('div', { 'aria-label': ariaLabel, 'data-chart': 'line', role: 'img' }),
}))

window.localStorage.setItem(LANGUAGE_STORAGE_KEY, 'en')
void i18n.changeLanguage('en')

Object.defineProperty(window, 'matchMedia', {
  configurable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
  writable: true,
})

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  window.localStorage.setItem(LANGUAGE_STORAGE_KEY, 'en')
  void i18n.changeLanguage('en')
  document.documentElement.classList.remove('dark')
  delete document.documentElement.dataset.theme
  document.documentElement.style.removeProperty('color-scheme')
})
