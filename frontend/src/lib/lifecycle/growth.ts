import type { Tone } from '$lib/components/ui/tone';
import { ROLLUP_RATIO_LABEL, type Growth } from './projection';

/** How each growth class reads: the old dashboard's three, in the theme's tones. */
export const GROWTH: Record<Growth, { label: string; tone: Tone; description: string }> = {
	bounded: {
		label: 'O(1) · bounded',
		tone: 'success',
		description:
			'Storage is capped: samples past the deletion window are deleted and nothing is rolled up, so the total levels off.'
	},
	linear_efficient: {
		label: 'O(n) · efficient',
		tone: 'warning',
		description: `Samples are capped by the deletion window; their daily and per-session rollups stay and keep accumulating, at roughly ${ROLLUP_RATIO_LABEL} of the raw rate.`
	},
	linear: {
		label: 'O(n) · linear',
		tone: 'danger',
		description:
			'Every raw sample is kept forever, so storage grows with time and with every device connected.'
	}
};
