<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLAnchorAttributes } from 'svelte/elements';
	import { buttonClass, type ButtonSize, type ButtonVariant } from './button';

	let {
		variant = 'primary',
		size = 'md',
		class: className,
		children,
		...rest
	}: HTMLAnchorAttributes & {
		variant?: ButtonVariant;
		size?: ButtonSize;
		children: Snippet;
	} = $props();
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -- the caller resolves -->
<a {...rest} class={buttonClass(variant, size, className)}>
	{@render children()}
</a>
