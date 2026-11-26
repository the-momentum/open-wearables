import { parseDate, type CalendarDate } from '@internationalized/date';
import { ICON_BUTTON } from './button';
import { CAPTION, HEADING } from './typography';

/** Dates read en-GB, as everywhere else here; the week starts on Monday to match. */
export const CALENDAR_LOCALE = 'en-GB';
export const WEEK_STARTS_ON = 1;

/** A `YYYY-MM-DD` day, as the URL and the API carry it, for a picker; blank or malformed is none. */
export function toDate(iso: string | null | undefined): CalendarDate | undefined {
	if (!iso) return undefined;
	try {
		return parseDate(iso);
	} catch {
		return undefined;
	}
}

/**
 * Commits a typed date as a form field would: on Enter, or once focus leaves
 * the whole field - not when it only moves to the next part or the trigger.
 */
export function commitTyped(commit: () => void) {
	return {
		onkeydown: (event: KeyboardEvent) => {
			if (event.key === 'Enter') commit();
		},
		onfocusout: (event: FocusEvent) => {
			const field = event.currentTarget as HTMLElement;
			if (!field.contains(event.relatedTarget as Node | null)) commit();
		}
	};
}

export const POPOVER =
	'z-50 rounded-lg border border-border bg-background p-3 text-foreground shadow-header';

export const CALENDAR = {
	header: 'mb-2 flex items-center justify-between gap-2',
	heading: HEADING,
	nav: `${ICON_BUTTON} hover:bg-surface-muted`,
	grid: 'border-collapse select-none',
	head: `${CAPTION} size-9 font-normal`
} as const;

// Today is underlined rather than coloured, so it never fights a selection's fill.
const DAY =
	'grid size-9 place-items-center rounded-md text-xs text-foreground tabular-nums transition-colors hover:bg-surface-muted data-disabled:pointer-events-none data-disabled:opacity-40 data-outside-month:text-muted-foreground data-today:font-medium data-today:underline data-today:underline-offset-4 data-unavailable:line-through';

/** One picked day is filled; hover keeps it filled, a shade lighter. */
export const DAY_SINGLE = `${DAY} data-selected:bg-inverted data-selected:text-inverted-foreground data-selected:hover:bg-inverted-hover`;

/**
 * A range fills its two ends and lays a band between them, square-cornered so
 * neighbouring days join up - also while the second end is still being pointed at.
 */
export const DAY_RANGE = [
	DAY,
	'data-highlighted:rounded-none data-highlighted:bg-surface-muted',
	'data-range-middle:rounded-none data-range-middle:bg-surface-muted',
	'data-selection-start:bg-inverted data-selection-start:text-inverted-foreground data-selection-start:hover:bg-inverted-hover',
	'data-selection-end:bg-inverted data-selection-end:text-inverted-foreground data-selection-end:hover:bg-inverted-hover'
].join(' ');

/** A typed date's parts: the one being edited is highlighted, the slashes recede. */
export const SEGMENT =
	'rounded-sm px-px tabular-nums focus:bg-surface-muted focus:outline-none data-invalid:text-danger data-[segment=literal]:px-0 data-[segment=literal]:text-muted-foreground';

/**
 * The box around typed segments or native inputs; size, fill and type step are
 * the caller's. Focus rings the whole box, not the part inside it.
 */
export const DATE_BOX =
	'inline-flex items-center gap-2 border border-border focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-ring';

/** A native date input inside that box, as a touch screen gets it. */
export const NATIVE_DATE =
	'min-w-0 bg-transparent tabular-nums focus:outline-none [&::-webkit-calendar-picker-indicator]:cursor-pointer [&::-webkit-calendar-picker-indicator]:opacity-50';

export const CALENDAR_TRIGGER =
	'grid size-5 shrink-0 place-items-center rounded-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:bg-surface-muted focus-visible:outline-none';
