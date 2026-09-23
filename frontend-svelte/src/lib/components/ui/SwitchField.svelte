<script lang="ts">
	import Switch from './Switch.svelte';

	let { label, checked = $bindable(false) }: { label: string; checked?: boolean } = $props();
</script>

<!-- One string for the words beside it and the switch's own name, so the two
     cannot say different things. -->
<label class="flex min-h-11 items-center gap-2.5 text-sm text-foreground/90">
	<Switch bind:checked {label} />
	{label}
</label>
