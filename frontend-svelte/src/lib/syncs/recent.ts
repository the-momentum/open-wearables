/**
 * Read wider than shown, because the provider filter runs over the window:
 * slicing to 20 first would let a busy provider crowd a quiet one out entirely.
 */
export const RECENT_WINDOW = 100;
export const RECENT_SHOWN = 20;
