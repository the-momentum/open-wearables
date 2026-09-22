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
