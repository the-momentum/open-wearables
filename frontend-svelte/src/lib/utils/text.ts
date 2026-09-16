const ACRONYMS = new Set(['vo2', 'sdnn', 'rmssd', 'hrv', 'bmi', 'uv', 'sdk', 'xml', 'api', 'id']);

/** `in_progress` → `In progress`, so a new backend enum value needs no change. */
export function humanise(slug: string): string {
	return slug
		.split('_')
		.map((word, index) => {
			if (ACRONYMS.has(word)) return word.toUpperCase();
			return index === 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word;
		})
		.join(' ');
}
