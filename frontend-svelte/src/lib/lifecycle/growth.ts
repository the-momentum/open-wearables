import type { Tone } from '$lib/components/ui/tone';
import { ARCHIVE_RATIO_LABEL, type Growth } from './projection';

/** How each growth class reads: the old dashboard's three, in the theme's tones. */
export const GROWTH: Record<Growth, { label: string; tone: Tone; description: string }> = {
	bounded: {
		label: 'O(1) · bounded',
		tone: 'success',
		description:
			'Storage is capped: data past the retention window is deleted, so the total levels off.'
	},
	linear_efficient: {
		label: 'O(n) · efficient',
		tone: 'warning',
		description: `Live data is capped by the archive window; daily aggregates keep accumulating, at roughly ${ARCHIVE_RATIO_LABEL} of the raw rate.`
	},
	linear: {
		label: 'O(n) · linear',
		tone: 'danger',
		description:
			'Every raw sample is kept forever, so storage grows with time and with every device connected.'
	}
};
