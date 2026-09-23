/**
 * The box a form control sits in, shared by `TextField` and `SearchField` so
 * the two cannot drift. Horizontal padding is the caller's: a search field
 * holds a glyph on the left, a plain one does not.
 */
export const FIELD =
	'min-h-11 w-full rounded-lg border border-border bg-surface text-sm placeholder:text-muted-foreground/60';
