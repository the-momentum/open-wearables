<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';

	let {
		label,
		value,
		options,
		onselect,
		labelled = true
	}: {
		label: string;
		value: string | number;
		options: { value: string | number; label: string }[];
		/** What to do with the new value — navigate, or change state in place. */
		onselect: (value: string) => void;
		/** False when something outside already captions it, as `FilterGroup` does. */
		labelled?: boolean;
	} = $props();

	const id = $props.id();
</script>

<div class="relative inline-flex items-center">
	<label
		class={labelled
			? 'sr-only text-xs text-muted-foreground/70 sm:not-sr-only sm:mr-1.5'
			: 'sr-only'}
		for={id}
	>
		{label}
	</label>
	<select
		{id}
		{value}
		onchange={(event) => onselect(event.currentTarget.value)}
		class="h-8 appearance-none rounded-md border border-border bg-surface pr-7 pl-2
			text-xs text-foreground tabular-nums"
	>
		{#each options as option (option.value)}
			<option value={option.value}>{option.label}</option>
		{/each}
	</select>
	<ChevronDown
		size={13}
		aria-hidden="true"
		class="pointer-events-none absolute right-2 text-muted-foreground"
	/>
</div>
