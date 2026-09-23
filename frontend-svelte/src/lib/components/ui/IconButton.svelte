<script lang="ts">
	import type { Component } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import Button from './Button.svelte';

	let {
		icon: Icon,
		label,
		danger = false,
		...rest
	}: HTMLButtonAttributes & {
		icon: Component;
		/** The whole accessible name: there is no text beside the glyph. */
		label: string;
		/** Quiet until the pointer is on it — deleting is a thing you can do, not
		 *  a thing to be invited to do. */
		danger?: boolean;
	} = $props();
</script>

<Button
	variant="outline"
	size="sm"
	aria-label={label}
	class={danger ? 'hover:border-danger/40 hover:text-danger' : undefined}
	{...rest}
>
	<Icon size={13} aria-hidden="true" />
</Button>
