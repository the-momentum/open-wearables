<script lang="ts">
	import type { Component } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import { cn } from '$lib/utils/cn';
	import { ICON_BUTTON } from './button';
	import { ICON } from './icon';

	let {
		icon: Icon,
		label,
		danger = false,
		type = 'button',
		class: className,
		...rest
	}: HTMLButtonAttributes & {
		icon: Component;
		/** The whole accessible name: there is no text beside the glyph. */
		label: string;
		/** Quiet until the pointer is on it - deleting is a thing you can do, not
		 *  a thing to be invited to do. */
		danger?: boolean;
	} = $props();
</script>

<button
	{type}
	aria-label={label}
	{...rest}
	class={cn(ICON_BUTTON, danger && 'hover:text-danger', className)}
>
	<Icon size={ICON.sm} aria-hidden="true" />
</button>
