<script lang="ts">
	let { expanded = $bindable(false), total }: { expanded?: boolean; total: number } = $props();
</script>

<button
	type="button"
	onclick={() => (expanded = !expanded)}
	class="text-xs text-muted-foreground transition-colors hover:text-foreground"
>
	{expanded ? 'Show fewer' : `Show all ${total}`}
</button>
