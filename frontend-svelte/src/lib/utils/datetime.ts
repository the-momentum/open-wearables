const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
	['year', 31_536_000_000],
	['month', 2_592_000_000],
	['day', 86_400_000],
	['hour', 3_600_000],
	['minute', 60_000]
];

const relative = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
const absolute = new Intl.DateTimeFormat('en-GB', {
	day: 'numeric',
	month: 'short',
	year: 'numeric'
});

export function formatRelativeTime(iso: string | null, now = Date.now()): string {
	if (!iso) return 'Never';

	const elapsed = new Date(iso).getTime() - now;
	if (Number.isNaN(elapsed)) return 'Never';

	for (const [unit, ms] of UNITS) {
		if (Math.abs(elapsed) >= ms) return relative.format(Math.round(elapsed / ms), unit);
	}
	return 'Just now';
}

export function formatDate(iso: string | null): string {
	if (!iso) return '—';
	const date = new Date(iso);
	return Number.isNaN(date.getTime()) ? '—' : absolute.format(date);
}

const stamp = new Intl.DateTimeFormat('en-GB', {
	day: 'numeric',
	month: 'short',
	year: 'numeric',
	hour: '2-digit',
	minute: '2-digit'
});

export function formatDateTime(iso: string | null): string {
	if (!iso) return '—';
	const date = new Date(iso);
	return Number.isNaN(date.getTime()) ? '—' : stamp.format(date);
}
