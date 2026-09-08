<script lang="ts">
	import { sourceIcon, sourceLabel } from '$lib/syncs/source';

	let { source }: { source: string } = $props();

	const Icon = $derived(sourceIcon(source));
	const name = $derived(sourceLabel(source));
</script>

<span class="shrink-0 text-muted-foreground/60" title={name}>
	<Icon size={13} aria-hidden="true" />
	<span class="sr-only">{name}</span>
</span>
