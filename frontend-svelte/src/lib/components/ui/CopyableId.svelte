<script lang="ts">
	import { MONO } from './typography';
	import CopyButton from './CopyButton.svelte';

	let {
		value,
		label = 'ID',
		visible = 4
	}: { value: string; label?: string; visible?: number } = $props();

	// An id short enough to print whole should not wear an ellipsis it has not earned.
	const shown = $derived(value.length > visible ? `${value.slice(0, visible)}…` : value);
</script>

<!-- z-10 keeps this above the row-wide overlay link, so copying does not also
     open the row. -->
<span class="relative z-10 inline-flex items-center gap-1">
	<code title={value} class="rounded bg-surface-muted px-1.5 py-0.5 text-foreground/80 {MONO}">
		{shown}
	</code>
	<CopyButton {value} {label} />
</span>
