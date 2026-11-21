import { CAPTION } from './typography';

/** The card a list or a table sits on: users, syncs, deliveries. */
export const LIST_FRAME = 'rounded-lg border border-border bg-card';

/** One row of such a list, ruled from the next and lit while the pointer is on it. */
export const LIST_ROW = 'border-b border-border transition-colors last:border-b-0 hover:bg-surface';

/** A table's header band. Not sticky: inside an `overflow-x` frame it would anchor to the frame. */
export const TABLE_HEAD = 'border-b border-border bg-surface';

/** A column header, in the design's tagline; the sorted one is `cn(TABLE_HEADER, 'text-foreground')`. */
export const TABLE_HEADER = `h-10 px-4 text-left font-normal whitespace-nowrap ${CAPTION}`;

export const TABLE_CELL = 'px-4 py-3';
