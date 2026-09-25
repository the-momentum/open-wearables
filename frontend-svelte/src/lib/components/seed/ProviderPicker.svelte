<script lang="ts">
	import type { ProviderBrand } from '$lib/providers/labels';
	import ProviderLogo from '$lib/components/providers/ProviderLogo.svelte';
	import NumberField from '$lib/components/ui/NumberField.svelte';
	import { tagClass } from '$lib/components/ui/chip';
	import { MICRO } from '$lib/components/ui/typography';
	import { MAX_CONNECTIONS } from '$lib/seed/catalogue';
	import { LIMITS } from '$lib/seed/draft';
	import { cn } from '$lib/utils/cn';
	import { toggled } from '$lib/utils/collect';

	let {
		providers,
		chosen = $bindable([]),
		connections = $bindable(2)
	}: {
		providers: ProviderBrand[];
		chosen?: string[];
		connections?: number;
	} = $props();

	const full = $derived(chosen.length >= MAX_CONNECTIONS);
</script>

<div class="flex flex-col gap-3">
	<div class="flex flex-col gap-1.5">
		<span class={MICRO}>Providers</span>
		<div class="flex flex-wrap gap-1.5">
			<button
				type="button"
				aria-pressed={chosen.length === 0}
				onclick={() => (chosen = [])}
				class={tagClass(chosen.length === 0)}
			>
				Any
			</button>
			{#each providers as provider (provider.provider)}
				{@const on = chosen.includes(provider.provider)}
				<button
					type="button"
					aria-pressed={on}
					disabled={!on && full}
					onclick={() => (chosen = toggled(chosen, provider.provider))}
					class={cn(tagClass(on), 'inline-flex items-center gap-1.5 disabled:opacity-40')}
				>
					<ProviderLogo {provider} size="xs" />
					{provider.name}
				</button>
			{/each}
		</div>
	</div>

	<!-- A picked list sets the count itself: the backend keeps the first
	     `num_connections`, so a separate number could only drop some. -->
	{#if chosen.length === 0}
		<NumberField
			label="Connections per user"
			bind:value={connections}
			min={LIMITS.connections[0]}
			max={LIMITS.connections[1]}
			unit="at random"
		/>
	{:else}
		<p class={MICRO}>
			Each user connects to all {chosen.length}.{#if full}
				That is the most a user can have.{/if}
		</p>
	{/if}
</div>
