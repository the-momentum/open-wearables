<script lang="ts">
	import { ICON } from '$lib/components/ui/icon';
	import { sourceIcon, sourceLabel } from '$lib/syncs/source';

	let { source }: { source: string } = $props();

	const Icon = $derived(sourceIcon(source));
	const name = $derived(sourceLabel(source));
</script>

<span class="shrink-0 text-muted-foreground" title={name}>
	<Icon size={ICON.xs} aria-hidden="true" />
	<span class="sr-only">{name}</span>
</span>
