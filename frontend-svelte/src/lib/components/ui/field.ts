/**
 * The box every form control sits in, so none can drift. Width and horizontal
 * padding are the caller's: a text field fills its row, a number is four
 * digits wide, and a search field holds a glyph on the left. Carrying `w-full`
 * here once meant a `w-24` beside it lost to stylesheet order.
 */
export const FIELD =
	'min-h-11 rounded-lg border border-border bg-surface text-sm placeholder:text-muted-foreground/60';
