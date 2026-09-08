/** `in_progress` → `In progress`, so a new backend enum value needs no frontend change. */
export function humanise(slug: string): string {
	const spaced = slug.replace(/_/g, ' ');
	return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
