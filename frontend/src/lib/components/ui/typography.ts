/** The smallest step in the scale: the design's text-tiny, 12px. */
export const TINY = 'text-xs';

/** Small print beside a chart or under a figure: axis ends, shares, cell labels. */
export const MICRO = `${TINY} text-muted-foreground`;

/** The small print under a section: how a figure was reached, what it leaves out. */
export const FOOTNOTE = `${TINY} text-muted-foreground/80`;

/** An id, a URL, an event name - anything read character by character. */
export const MONO = `${TINY} font-mono`;

/** An id or a key prefix set on its own grey chip. */
export const ID_CHIP = `rounded bg-surface-muted px-1.5 py-0.5 leading-4 text-secondary-foreground ${MONO}`;

/** A small action set in running text - a group's "all", a "select all". */
export const TEXT_LINK = `${MICRO} underline-offset-2 hover:text-foreground hover:underline`;

/** A link inside a sentence, in the accent so it reads as one. */
export const INLINE_LINK = 'text-primary hover:underline';

/** The micro heading above a figure, a pane, a filter group or a table column: the design's tagline-small. */
export const CAPTION = 'font-mono text-xs leading-tagline text-muted-foreground uppercase';

/** What a card is called: a section's heading, and an accordion card's title. */
export const HEADING = 'text-sm font-medium text-foreground';

/** What a panel or a dashboard card is called: the design's h6. */
export const TITLE = 'text-lg font-medium text-foreground';

/** The headline figure of a stat card: the design's h3. */
export const STAT = 'text-4xl font-medium text-foreground tabular-nums';

/** A tooltip bubble: a hint's, and a chart's reading under the pointer. */
export const TOOLTIP =
	'rounded-lg bg-inverted px-2.5 py-1.5 text-xs text-inverted-foreground shadow-md';

/** A one-line explanation standing in for content that is not there. */
export const NOTE = 'py-6 text-center text-sm text-muted-foreground';

/** A pagination step, and the same square greyed out once it leads nowhere. */
export const STEP =
	'grid size-10 place-items-center rounded-lg border border-border text-foreground transition-colors hover:bg-surface-muted';

export const STEP_SPENT =
	'grid size-10 place-items-center rounded-lg border border-border text-muted-foreground';
