/**
 * A tinted background with the foreground that belongs to it. Written out three
 * times before this existed — badges, status pills and tile icons — with the
 * same colour under two names.
 */
export type Tone = 'primary' | 'success' | 'warning' | 'danger' | 'neutral' | 'muted';

export const TONE: Record<Tone, string> = {
	primary: 'bg-primary/12 text-primary',
	success: 'bg-success/12 text-success',
	warning: 'bg-warning/15 text-warning',
	danger: 'bg-danger/12 text-danger',
	neutral: 'bg-surface-muted text-muted-foreground',
	muted: 'bg-surface-muted text-foreground/70'
};

/** The same tones as a raw colour, for a stroke or a figure that is not a pill. */
export const TONE_COLOUR: Record<Tone, string> = {
	primary: 'var(--color-primary)',
	success: 'var(--color-success)',
	warning: 'var(--color-warning)',
	danger: 'var(--color-danger)',
	neutral: 'var(--color-muted-foreground)',
	muted: 'var(--color-muted-foreground)'
};
