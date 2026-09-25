<script lang="ts">
	import type { ProviderBrand } from '$lib/providers/labels';
	import UsersIcon from '@lucide/svelte/icons/users';
	import Card from '$lib/components/ui/Card.svelte';
	import NumberField from '$lib/components/ui/NumberField.svelte';
	import { LIMITS, type Draft } from '$lib/seed/draft';
	import ProviderPicker from './ProviderPicker.svelte';
	import WindowPicker from './WindowPicker.svelte';

	let {
		draft = $bindable(),
		providers
	}: {
		draft: Draft;
		providers: ProviderBrand[];
	} = $props();
</script>

<Card icon={UsersIcon} title="Who and when">
	<div class="grid gap-5 lg:grid-cols-2">
		<div class="flex flex-col gap-4">
			<NumberField
				label="Users"
				bind:value={draft.users}
				min={LIMITS.users[0]}
				max={LIMITS.users[1]}
				unit="users"
			/>
			<WindowPicker bind:value={draft.window} />
			<NumberField
				label="Seed"
				placeholder="Random"
				min={0}
				hint="The same seed with the same settings makes the same users again."
				bind:value={draft.seed}
			/>
		</div>

		<ProviderPicker
			{providers}
			bind:chosen={draft.providers}
			bind:connections={draft.connections}
		/>
	</div>
</Card>
