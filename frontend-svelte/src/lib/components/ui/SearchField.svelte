<script lang="ts">
	import Search from '@lucide/svelte/icons/search';
	import { goto } from '$app/navigation';

	let {
		value: current,
		hrefFor,
		label,
		placeholder,
		hidden = {}
	}: {
		value: string;
		hrefFor: (term: string) => string;
		label: string;
		placeholder?: string;
		/** Carried through by the no-JS form submit, which posts only its own fields. */
		hidden?: Record<string, string>;
	} = $props();

	const DEBOUNCE_MS = 300;

	// Writable derived: typing overwrites it, and it re-syncs whenever the URL
	// changes from elsewhere, such as Back.
	let value = $derived(current);
	let timer: ReturnType<typeof setTimeout> | undefined;

	$effect(() => () => clearTimeout(timer));

	function submit() {
		clearTimeout(timer);
		// replaceState: typing must not leave one history entry per keystroke.
		// SvelteKit aborts a superseded navigation, so a slow response cannot
		// overwrite a newer one.
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- hrefFor resolves
		goto(hrefFor(value.trim()), { replaceState: true, keepFocus: true, noScroll: true });
	}
</script>

<form
	class="relative"
	onsubmit={(event) => {
		event.preventDefault();
		submit();
	}}
>
	<Search
		size={16}
		aria-hidden="true"
		class="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted-foreground"
	/>
	<input
		type="search"
		name="search"
		bind:value
		oninput={() => {
			clearTimeout(timer);
			timer = setTimeout(submit, DEBOUNCE_MS);
		}}
		aria-label={label}
		{placeholder}
		class="min-h-11 w-full rounded-lg border border-border bg-surface
			pr-3 pl-9 text-sm placeholder:text-muted-foreground/60"
	/>
	{#each Object.entries(hidden) as [name, fieldValue] (name)}
		<input type="hidden" {name} value={fieldValue} />
	{/each}
</form>
