import { apiGet } from './api';
import type { Coverage } from '$lib/coverage/types';

/**
 * What every provider can deliver. Static — the backend builds it from the
 * provider strategies once and `lru_cache`s it, and it changes only on deploy —
 * and about 15 KB, so there is nothing here to page or narrow server-side.
 */
export const fetchCoverage = (accessToken: string) =>
	apiGet<Coverage>('/api/v1/meta/coverage', accessToken);
