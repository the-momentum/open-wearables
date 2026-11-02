<script lang="ts">
	let {
		checked = $bindable(false),
		label,
		disabled = false,
		onchange
	}: {
		checked?: boolean;
		/** Named for assistive tech; the visible text is the caller's own. */
		label: string;
		disabled?: boolean;
		onchange?: (next: boolean) => void;
	} = $props();

	function toggle() {
		checked = !checked;
		onchange?.(checked);
	}
</script>

<!-- role="switch" rather than a styled checkbox: it announces on/off, and the
     track is the whole target rather than a 16px box inside it. -->
<button
	type="button"
	role="switch"
	aria-checked={checked}
	aria-label={label}
	{disabled}
	onclick={toggle}
	class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors
		disabled:cursor-not-allowed disabled:opacity-50
		{checked ? 'bg-primary' : 'bg-surface-muted ring-1 ring-border'}"
>
	<span
		aria-hidden="true"
		class="size-4 rounded-full bg-white shadow-sm transition-transform
			{checked ? 'translate-x-6' : 'translate-x-1'}"
	></span>
</button>
