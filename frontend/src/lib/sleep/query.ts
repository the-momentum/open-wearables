/** Which sessions the list shows. The backend's `is_nap`, with "all" leaving it off. */
export type SessionFilter = 'all' | 'night' | 'nap';

export const sessionFilter = (params: URLSearchParams): SessionFilter => {
	const asked = params.get('kind');
	return asked === 'night' || asked === 'nap' ? asked : 'all';
};

/** `is_nap` as the API reads it, or null to send nothing and get both. */
export const isNapParam = (filter: SessionFilter): string | null =>
	filter === 'all' ? null : String(filter === 'nap');
