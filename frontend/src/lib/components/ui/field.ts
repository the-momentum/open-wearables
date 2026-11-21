/**
 * The box every form control sits in, so none can drift. Width and horizontal
 * padding are the caller's: a text field fills its row, a number is four
 * digits wide, and a search field holds a glyph on the left. Carrying `w-full`
 * here once meant a `w-24` beside it lost to stylesheet order.
 */
export const FIELD =
	'min-h-11 rounded-lg border border-border bg-background text-sm transition-colors placeholder:text-muted-foreground hover:border-surface-strong md:min-h-10';

// `appearance` is app.css's: the open list is styled there, where supported.
const SELECT_BOX =
	'border border-border bg-background pr-7 pl-2 text-xs text-foreground tabular-nums transition-colors hover:border-surface-strong';

/**
 * A native select with room for a drawn chevron on the right: a filter above a
 * list (`md`), and the per-page picker beside a pager (`sm`).
 */
export const SELECT = {
	md: `${SELECT_BOX} h-9 rounded-lg`,
	sm: `${SELECT_BOX} h-8 rounded-md`
} as const;
