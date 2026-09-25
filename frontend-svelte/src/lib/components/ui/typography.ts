/** The smallest step in the scale. Written as both 11px and 0.6875rem before. */
export const TINY = 'text-[11px]';

/** Small print beside a chart or under a figure: axis ends, shares, cell labels. */
export const MICRO = `${TINY} text-muted-foreground`;

/** The small print under a section: how a figure was reached, what it leaves out. */
export const FOOTNOTE = `${TINY} text-muted-foreground/80`;

/** An id, a URL, an event name — anything read character by character. */
export const MONO = `${TINY} font-mono`;

/** A small action set in running text — a group's "all", a "select all". */
/** A link inside a sentence, in the accent so it reads as one. */
export const INLINE_LINK = 'text-primary hover:underline';

export const TEXT_LINK = `${MICRO} underline-offset-2 hover:text-foreground hover:underline`;

/** The micro heading used above a figure, a pane or a filter group. */
export const CAPTION =
	'text-[10px] font-semibold tracking-wider text-muted-foreground/70 uppercase';

/** What a card is called: a section's heading, and an accordion card's title. */
export const HEADING = 'text-sm font-semibold text-foreground';

/** A one-line explanation standing in for content that is not there. */
export const NOTE = 'py-6 text-center text-sm text-muted-foreground';

/** A pagination step, and the same square greyed out once it leads nowhere. */
export const STEP =
	'border-border hover:bg-surface-muted grid size-10 place-items-center rounded-lg border transition-colors';

export const STEP_SPENT =
	'border-border text-muted-foreground/40 grid size-10 place-items-center rounded-lg border';
