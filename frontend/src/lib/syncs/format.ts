import type { Tone } from '$lib/components/ui/tone';
import type { SyncRunSummary } from './types';

const TONE: Record<string, Tone> = {
	success: 'success',
	partial: 'warning',
	stale: 'warning',
	unfinished: 'warning',
	in_progress: 'primary',
	failed: 'danger',
	cancelled: 'neutral',
	skipped: 'neutral'
};

export const statusTone = (status: string): Tone => TONE[status] ?? 'neutral';

export const isRunning = (status: string) => status === 'in_progress';

/** "40/100", or just "40" when the provider never said how many there are. */
export const itemsLabel = (run: Pick<SyncRunSummary, 'items_processed' | 'items_total'>) =>
	run.items_processed === null
		? null
		: run.items_total === null
			? String(run.items_processed)
			: `${run.items_processed}/${run.items_total}`;

export function formatDuration(startIso: string | null, endIso: string | null): string | null {
	if (!startIso || !endIso) return null;

	const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
	if (Number.isNaN(ms) || ms < 0) return null;
	if (ms < 1000) return '<1s';

	const seconds = Math.round(ms / 1000);
	if (seconds < 60) return `${seconds}s`;

	const minutes = Math.floor(seconds / 60);
	if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
	return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

// UTC: the backend records the window in UTC, so rendering it locally would
// shift a midnight boundary onto the wrong day.
const windowFormat = new Intl.DateTimeFormat('en-GB', {
	day: 'numeric',
	month: 'short',
	timeZone: 'UTC'
});

/** The span of data a run covered, as opposed to when it ran. */
export function formatWindow(startIso: string | null, endIso: string | null): string | null {
	if (!startIso || !endIso) return null;

	const start = new Date(startIso);
	const end = new Date(endIso);
	if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null;

	if (start.getUTCFullYear() === end.getUTCFullYear()) {
		return `${windowFormat.format(start)} – ${windowFormat.format(end)} ${end.getUTCFullYear()}`;
	}
	return (
		`${windowFormat.format(start)} ${start.getUTCFullYear()} – ` +
		`${windowFormat.format(end)} ${end.getUTCFullYear()}`
	);
}
