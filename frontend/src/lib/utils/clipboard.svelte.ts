const RESET_MS = 2000;

/**
 * Copy-and-confirm: writes to the clipboard and flips `copied` for a moment.
 * Runes only work in `.svelte`/`.svelte.ts`, hence the extension.
 */
export function createCopier(resetMs = RESET_MS) {
	let copied = $state(false);
	let timer: ReturnType<typeof setTimeout> | undefined;

	$effect(() => () => clearTimeout(timer));

	return {
		get copied() {
			return copied;
		},
		async copy(text: string) {
			try {
				await navigator.clipboard.writeText(text);
				copied = true;
				clearTimeout(timer);
				timer = setTimeout(() => (copied = false), resetMs);
			} catch {
				// Clipboard access can be denied; there is nothing useful to say.
			}
		}
	};
}
