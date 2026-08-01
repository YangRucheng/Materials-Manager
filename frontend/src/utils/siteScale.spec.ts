import { beforeEach, describe, expect, it } from 'vitest'
import {
  DEFAULT_SITE_SCALE,
  SITE_SCALE_STORAGE_KEY,
  loadSiteScale,
  normalizeSiteScale,
  saveSiteScale,
} from './siteScale'

describe('site scale', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.style.zoom = ''
  })

  it('normalizes invalid and out-of-range values', () => {
    expect(normalizeSiteScale('invalid')).toBe(DEFAULT_SITE_SCALE)
    expect(normalizeSiteScale(30)).toBe(60)
    expect(normalizeSiteScale(180)).toBe(120)
    expect(normalizeSiteScale(92.6)).toBe(93)
  })

  it('saves locally and applies the scale', () => {
    expect(saveSiteScale(90)).toBe(90)
    expect(localStorage.getItem(SITE_SCALE_STORAGE_KEY)).toBe('90')
    expect(document.documentElement.style.zoom).toBe('0.9')
  })

  it('restores the saved scale', () => {
    localStorage.setItem(SITE_SCALE_STORAGE_KEY, '115')
    expect(loadSiteScale()).toBe(115)
    expect(document.documentElement.style.zoom).toBe('1.15')
  })
})
