const decimalPattern = /^\d+(?:\.\d)?$/

export function isDecimalString(value: string, decimalPlaces = 1, allowZero = false): boolean {
  if (!decimalPattern.test(value)) return false
  const [integer, fraction = ''] = value.split('.')
  if (fraction.length > decimalPlaces || integer.length > 18) return false
  return allowZero ? compareDecimal(value, '0') >= 0 : compareDecimal(value, '0') > 0
}

export function decimalPlacesOf(value: string): number {
  return value.split('.')[1]?.length ?? 0
}

export function normalizeDecimal(value: string): string {
  if (!value) return '0'
  const [whole, fraction = ''] = value.split('.')
  const cleanWhole = whole.replace(/^0+(?=\d)/, '') || '0'
  const cleanFraction = fraction.replace(/0+$/, '')
  return cleanFraction ? `${cleanWhole}.${cleanFraction}` : cleanWhole
}

function parts(value: string): [bigint, bigint, number] {
  const [whole, fraction = ''] = normalizeDecimal(value).split('.')
  return [BigInt(whole), BigInt(fraction || 0), fraction.length]
}

export function compareDecimal(a: string, b: string): number {
  const [aw, af, as] = parts(a)
  const [bw, bf, bs] = parts(b)
  const scale = Math.max(as, bs)
  const av = aw * 10n ** BigInt(scale) + af * 10n ** BigInt(scale - as)
  const bv = bw * 10n ** BigInt(scale) + bf * 10n ** BigInt(scale - bs)
  return av === bv ? 0 : av > bv ? 1 : -1
}

export function subtractDecimal(a: string, b: string): string {
  const scale = Math.max(decimalPlacesOf(a), decimalPlacesOf(b))
  const factor = 10n ** BigInt(scale)
  const toScaled = (value: string) => {
    const [w, f = ''] = value.split('.')
    return BigInt(w) * factor + BigInt(f.padEnd(scale, '0') || 0)
  }
  const result = toScaled(a) - toScaled(b)
  const negative = result < 0n
  const absolute = negative ? -result : result
  const whole = absolute / factor
  const fraction = (absolute % factor).toString().padStart(scale, '0').replace(/0+$/, '')
  return `${negative ? '-' : ''}${whole}${fraction ? `.${fraction}` : ''}`
}
