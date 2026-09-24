export const THEMES = ['system', 'light', 'dark'] as const;
export type Theme = (typeof THEMES)[number];

/** A cookie, not localStorage, so the server can render the right class first. */
export const THEME_COOKIE = 'ow-theme';

const YEAR_SECONDS = 60 * 60 * 24 * 365;

export const parseTheme = (value: string | undefined): Theme =>
	THEMES.includes(value as Theme) ? (value as Theme) : 'system';

/** The class on <html>; none leaves it to the OS through the media query. */
export const themeClass = (theme: Theme) => (theme === 'system' ? '' : theme);

/** In the browser: swaps the class, and keeps the choice for the server's next render. */
export function applyTheme(theme: Theme) {
	const root = document.documentElement;
	root.classList.remove('light', 'dark');
	if (themeClass(theme)) root.classList.add(themeClass(theme));
	document.cookie =
		theme === 'system'
			? `${THEME_COOKIE}=; path=/; max-age=0; samesite=lax`
			: `${THEME_COOKIE}=${theme}; path=/; max-age=${YEAR_SECONDS}; samesite=lax`;
}
