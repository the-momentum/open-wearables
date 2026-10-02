/** What every day count and every seed field here accepts: a whole number, bounds included. */
export const isWholeIn = (value: number, low: number, high: number) =>
	Number.isInteger(value) && value >= low && value <= high;
