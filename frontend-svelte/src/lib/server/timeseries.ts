import { apiGet } from './api';
import { resolutionFor, type Sample } from '$lib/timeseries/samples';

type SamplePage = { data: Sample[]; pagination: { total_count: number | null } };

/** The endpoint's own ceiling, and what one curve is allowed to cost. */
const PAGE = 1000;

export type FetchedSamples = {
	samples: Sample[];
	/** What the readings are: stored values, or averages over a bucket. */
	resolution: string;
	/** The window holds more than a page, so the curve is missing detail. */
	truncated: boolean;
};

export async function fetchSamples(
	userId: string,
	accessToken: string,
	window: { from: string; to: string; seconds: number; types: string[] },
	provider: string
): Promise<FetchedSamples> {
	const load = async (resolution: string) => {
		const params = new URLSearchParams({
			start_time: window.from,
			end_time: window.to,
			resolution,
			limit: String(PAGE)
		});
		for (const type of window.types) params.append('types', type);
		// Without this a phone worn alongside the watch adds its own lines, and
		// the question here is what the workout's own device recorded.
		if (provider) params.set('provider', provider);

		const page = await apiGet<SamplePage>(
			`/api/v1/users/${userId}/timeseries?${params}`,
			accessToken
		);
		const total = page.pagination.total_count ?? page.data.length;
		return { samples: page.data, resolution, truncated: total > page.data.length };
	};

	// Stored readings first: a minute average smooths exactly the spikes an admin
	// opened the chart to look at. Only when they do not fit does the curve get
	// bucketed, and then it says so.
	const raw = await load('raw');
	return raw.truncated ? load(resolutionFor(window.seconds)) : raw;
}

/**
 * A samples endpoint: fetched when a card opens, not with the list, because ten
 * cards' worth of curves is ten timeseries scans for the nine nobody expands.
 */
export function samplesFor(url: URL, types: string[]) {
	const from = url.searchParams.get('from') ?? '';
	const to = url.searchParams.get('to') ?? '';

	if (!from || !to) return null;

	return {
		window: { from, to, seconds: Number(url.searchParams.get('seconds') ?? 0), types },
		provider: url.searchParams.get('provider') ?? ''
	};
}

/** What an empty window answers, so a caller need not shape it twice. */
export const NO_SAMPLES: FetchedSamples = { samples: [], resolution: 'raw', truncated: false };
