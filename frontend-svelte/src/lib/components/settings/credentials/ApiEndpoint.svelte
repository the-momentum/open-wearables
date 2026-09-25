<script lang="ts">
	import Globe from '@lucide/svelte/icons/globe';
	import CopyButton from '$lib/components/ui/CopyButton.svelte';
	import { MICRO, MONO } from '$lib/components/ui/typography';
	import { publicApiUrl } from '$lib/config/public-api';

	// VITE_API_URL — what a browser or a phone dials, never the server's own hop.
	const url = publicApiUrl();

	// A key is worth nothing until you know which header it goes in, and the old
	// dashboard left that to the docs.
	const facts = $derived([
		{ label: 'API base URL', value: url || 'Not configured — set VITE_API_URL here.', copy: url },
		{
			label: 'Send a key as',
			value: 'Authorization: Bearer <your API key>',
			copy: 'Authorization: Bearer <your API key>'
		}
	]);
</script>

<!-- Not a card: it is the address the sections below hang off, so it reads as
     the page's standing fact rather than a third thing to manage. -->
<div
	class="grid grid-cols-[2rem_1fr_auto] items-center gap-x-3 gap-y-3 rounded-xl border
		border-border bg-surface-muted/40 p-4"
>
	<span
		aria-hidden="true"
		class="grid size-8 place-items-center rounded-lg bg-primary/10 text-primary"
	>
		<Globe size={16} />
	</span>

	{#each facts as fact, index (fact.label)}
		{#if index > 0}
			<!-- The rule spans all three columns, so the glyph column stays empty
			     under the mark rather than needing a spacer element. -->
			<div class="col-span-3 border-t border-border/70"></div>
			<span></span>
		{/if}

		<div class="min-w-0">
			<span class={MICRO}>{fact.label}</span>
			<code class="block truncate text-sm text-foreground/90 {MONO}">{fact.value}</code>
		</div>

		{#if fact.copy}
			<CopyButton value={fact.copy} label={fact.label} />
		{:else}
			<span></span>
		{/if}
	{/each}
</div>
