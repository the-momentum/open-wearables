/**
 * Appends non-null, non-empty values to URLSearchParams
 */
export function appendSearchParams(
  searchParams: URLSearchParams,
  params: Record<string, string | number | undefined | null>
): void {
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') {
      searchParams.set(key, String(value));
    }
  }
}
