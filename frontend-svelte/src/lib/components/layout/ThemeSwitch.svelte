<script lang="ts">
	import Monitor from '@lucide/svelte/icons/monitor';
	import Moon from '@lucide/svelte/icons/moon';
	import Sun from '@lucide/svelte/icons/sun';
	import { page } from '$app/state';
	import { applyTheme, type Theme } from '$lib/theme';
	import { cn } from '$lib/utils/cn';

	const OPTIONS = [
		{ value: 'system', label: 'Auto', icon: Monitor },
		{ value: 'light', label: 'Light', icon: Sun },
		{ value: 'dark', label: 'Dark', icon: Moon }
	] as const;

	// Seeded from the cookie the server read; from then on the click owns it.
	let theme = $state<Theme>(page.data.theme ?? 'system');
	const at = $derived(OPTIONS.findIndex((option) => option.value === theme));

	function choose(next: Theme) {
		theme = next;
		applyTheme(next);
	}
</script>

<div
	role="group"
	aria-label="Theme"
	class="relative inline-flex shrink-0 rounded-full border border-border bg-surface-muted p-0.5"
>
	<!-- One thumb that slides, rather than three buttons that each light up. -->
	<span
		aria-hidden="true"
		class="absolute top-0.5 left-0.5 size-7 rounded-full bg-surface shadow-sm ring-1 ring-border/70
			transition-transform duration-200 ease-out"
		style="transform: translateX({at * 100}%)"
	></span>
	{#each OPTIONS as option (option.value)}
		{@const active = option.value === theme}
		<button
			type="button"
			aria-label={option.label}
			aria-pressed={active}
			title={option.label}
			onclick={() => choose(option.value)}
			class={cn(
				'relative grid size-7 place-items-center rounded-full transition-colors',
				active ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
			)}
		>
			<option.icon size={14} aria-hidden="true" />
		</button>
	{/each}
</div>
