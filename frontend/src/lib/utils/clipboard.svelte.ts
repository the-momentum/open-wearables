const RESET_MS = 2000;

/**
 * Copy-and-confirm: writes to the clipboard and flips `copied` for a moment.
 * Runes only work in `.svelte`/`.svelte.ts`, hence the extension.
 */
export function createCopier(resetMs = RESET_MS) {
	let copied = $state(false);
	let timer: ReturnType<typeof setTimeout> | undefined;

	$effect(() => () => clearTimeout(timer));

	function confirm() {
		copied = true;
		clearTimeout(timer);
		timer = setTimeout(() => (copied = false), resetMs);
	}

	return {
		get copied() {
			return copied;
		},
		async copy(text: string) {
			try {
				await navigator.clipboard.writeText(text);
				confirm();
			} catch {
				// Clipboard access can be denied; there is nothing useful to say.
			}
		},
		/**
		 * For text that has to be fetched first. Safari drops the click's permission
		 * across an await, so the pending text goes into the ClipboardItem instead.
		 */
		async copyPending(text: Promise<string>) {
			try {
				const blob = text.then((value) => new Blob([value], { type: 'text/plain' }));
				await navigator.clipboard.write([new ClipboardItem({ 'text/plain': blob })]);
				confirm();
			} catch {
				// Clipboard access can be denied; there is nothing useful to say.
			}
		}
	};
}
