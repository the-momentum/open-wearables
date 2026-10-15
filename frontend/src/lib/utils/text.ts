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

/** The word for a count of it: 1 day, 2 days. Regular plurals only, which is all this app needs. */
export const noun = (count: number, word: string) => (count === 1 ? word : `${word}s`);

export const plural = (count: number, word: string) => `${count} ${noun(count, word)}`;
