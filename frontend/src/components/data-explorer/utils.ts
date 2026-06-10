import type { SourceMetadata } from '@/lib/api/types';

/** Format a snake_case code (series type, provider, workout type) for display. */
export function formatLabel(code: string | null | undefined): string {
  if (!code) return '—';
  return code.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Format a source (provider + optional device) for display. */
export function formatSource(
  source:
    | SourceMetadata
    | { provider: string; device?: string | null }
    | null
    | undefined
): string {
  if (!source) return '—';
  const provider = formatLabel(source.provider);
  return source.device ? `${provider} · ${source.device}` : provider;
}

/** Format a numeric sample value with at most 2 decimal places. */
export function formatValue(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}
