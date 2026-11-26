/**
 * The design's icon sizes in px, for Lucide's `size`; nothing in between. The
 * stroke stays 1px at every size (`setLucideProps` in the root layout), so
 * emphasis comes from colour or a bigger step.
 */
export const ICON = { xs: 12, sm: 16, md: 20, lg: 24, xl: 32, xxl: 40 } as const;

/** An icon on a tinted square, leading a card or a row. */
export const ICON_TILE =
	'grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary';
