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

	// Halves of the row on a phone, where the sheet is the screen's width.
	const SHARE = 'flex-1 sm:flex-none';
</script>

<!-- Cancel first, confirm last: the destructive one should not be where a thumb
     lands by habit. -->
<div class="flex justify-end gap-2">
	<Button variant="outline" class={SHARE} onclick={oncancel}>Cancel</Button>
	<Button
		type="submit"
		variant={destructive ? 'danger' : 'primary'}
		disabled={submitting}
		class={SHARE}
	>
		{submitting ? busyLabel : submitLabel}
	</Button>
</div>
