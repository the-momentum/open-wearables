<script lang="ts">
	import Button from './Button.svelte';

	let {
		oncancel,
		submitting,
		submitLabel,
		busyLabel,
		destructive = false
	}: {
		oncancel: () => void;
		submitting: boolean;
		submitLabel: string;
		busyLabel: string;
		destructive?: boolean;
	} = $props();
</script>

<!-- Cancel first, confirm last: the destructive one should not be where a thumb
     lands by habit. -->
<div class="mt-1 flex justify-end gap-2">
	<Button variant="outline" onclick={oncancel}>Cancel</Button>
	<Button
		type="submit"
		disabled={submitting}
		class={destructive ? 'bg-danger text-danger-foreground hover:bg-danger/90' : undefined}
	>
		{submitting ? busyLabel : submitLabel}
	</Button>
</div>
