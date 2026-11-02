/** The smallest step in the scale: the design's text-tiny, 12px. */
export const TINY = 'text-xs';

/** Small print beside a chart or under a figure: axis ends, shares, cell labels. */
export const MICRO = `${TINY} text-muted-foreground`;

/** The small print under a section: how a figure was reached, what it leaves out. */
export const FOOTNOTE = `${TINY} text-muted-foreground/80`;

/** An id, a URL, an event name - anything read character by character. */
export const MONO = `${TINY} font-mono`;

/** A small action set in running text - a group's "all", a "select all". */
export const TEXT_LINK = `${MICRO} underline-offset-2 hover:text-foreground hover:underline`;

/** A link inside a sentence, in the accent so it reads as one. */
export const INLINE_LINK = 'text-primary hover:underline';

/** The micro heading above a figure, a pane, a filter group or a column: the design's tagline-small. */
export const CAPTION = 'font-mono text-xs leading-[1.3] text-muted-foreground uppercase';

/** What a card is called: a section's heading, and an accordion card's title. */
export const HEADING = 'text-sm font-medium text-foreground';

/** A one-line explanation standing in for content that is not there. */
export const NOTE = 'py-6 text-center text-sm text-muted-foreground';

/** A pagination step, and the same square greyed out once it leads nowhere. */
export const STEP =
	'border-border hover:bg-surface-muted grid size-10 place-items-center rounded-lg border transition-colors';

export const STEP_SPENT =
	'border-border text-muted-foreground/40 grid size-10 place-items-center rounded-lg border';
