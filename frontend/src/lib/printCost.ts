import type { ApiDecimal } from '../types/spool'

const UNIT_COST_SCALE = 1_000_000n
const MATERIAL_COST_SCALE = 10_000n

type DecimalParts = {
  numerator: bigint
  scale: bigint
}

export type EstimatedMaterialCost = {
  filamentCostPerG: string
  materialCost: string
}

export type CurrencyCostTotal = {
  currency: string
  amount: string
}

function decimalParts(value: ApiDecimal | string): DecimalParts | null {
  const normalized = String(value).trim()
  const match = /^(\d+)(?:\.(\d*))?$/.exec(normalized)
  if (!match) return null

  const fraction = match[2] ?? ''
  return {
    numerator: BigInt(`${match[1]}${fraction}`),
    scale: 10n ** BigInt(fraction.length),
  }
}

function roundHalfUp(numerator: bigint, denominator: bigint): bigint {
  const quotient = numerator / denominator
  const remainder = numerator % denominator
  return remainder * 2n >= denominator ? quotient + 1n : quotient
}

function fixed(value: bigint, decimalPlaces: number): string {
  const digits = value.toString().padStart(decimalPlaces + 1, '0')
  return `${digits.slice(0, -decimalPlaces)}.${digits.slice(-decimalPlaces)}`
}

/**
 * Mirrors the backend snapshot rule exactly: cost/gram is rounded HALF_UP to
 * six decimal places before material cost is rounded HALF_UP to four places.
 */
export function calculateEstimatedMaterialCost(
  purchasePrice: ApiDecimal | null,
  initialFilamentWeightG: ApiDecimal,
  estimatedWeightG: ApiDecimal | string,
): EstimatedMaterialCost | null {
  if (purchasePrice === null || String(estimatedWeightG).trim() === '') return null

  const price = decimalParts(purchasePrice)
  const initialWeight = decimalParts(initialFilamentWeightG)
  const estimatedWeight = decimalParts(estimatedWeightG)
  if (!price || !initialWeight || !estimatedWeight || initialWeight.numerator === 0n) return null

  const costPerGram = roundHalfUp(
    price.numerator * initialWeight.scale * UNIT_COST_SCALE,
    price.scale * initialWeight.numerator,
  )
  const materialCost = roundHalfUp(
    costPerGram * estimatedWeight.numerator * MATERIAL_COST_SCALE,
    UNIT_COST_SCALE * estimatedWeight.scale,
  )

  return {
    filamentCostPerG: fixed(costPerGram, 6),
    materialCost: fixed(materialCost, 4),
  }
}

export function sumEstimatedCostsByCurrency(
  costs: readonly { currency: string; materialCost: string }[],
): CurrencyCostTotal[] {
  const totals = new Map<string, bigint>()

  for (const cost of costs) {
    const amount = decimalParts(cost.materialCost)
    if (!amount) continue
    const scaledAmount = amount.scale === MATERIAL_COST_SCALE
      ? amount.numerator
      : roundHalfUp(amount.numerator * MATERIAL_COST_SCALE, amount.scale)
    totals.set(cost.currency, (totals.get(cost.currency) ?? 0n) + scaledAmount)
  }

  return [...totals.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([currency, amount]) => ({ currency, amount: fixed(amount, 4) }))
}
