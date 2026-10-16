import { apiGet } from './api';
import type { DataSource } from '$lib/sources/types';

/** `{ items, total }`; the page needs only the rows. */
export const fetchDataSources = async (userId: string, accessToken: string) =>
	(await apiGet<{ items: DataSource[] }>(`/api/v1/users/${userId}/data-sources`, accessToken))
		.items;
