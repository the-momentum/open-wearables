<script lang="ts">
	import Trash2 from '@lucide/svelte/icons/trash-2';

	let { label, onclick }: { label: string; onclick: () => void } = $props();
</script>

<!-- Quiet until the pointer is on it: deleting a record is a thing to be able to
     do, not a thing to be invited to do. -->
<button
	type="button"
	{onclick}
	class="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors
		hover:text-danger"
>
	<Trash2 size={14} aria-hidden="true" />
	{label}
</button>
