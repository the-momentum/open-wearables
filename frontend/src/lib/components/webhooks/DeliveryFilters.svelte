<script lang="ts">
	import { goto } from '$app/navigation';
	import FilterGroup from '$lib/components/filters/FilterGroup.svelte';
	import FilterSelect from '$lib/components/ui/FilterSelect.svelte';
	import { STATUS_OPTIONS } from '$lib/webhooks/status';
	import type { EventType } from '$lib/webhooks/types';

	let {
		status,
		eventType,
		types,
		hrefFor
	}: {
		status: string;
		eventType: string;
		types: EventType[];
		hrefFor: (changes: Record<string, string | null>) => string;
	} = $props();

	const statuses = [{ value: '', label: 'Any status' }, ...STATUS_OPTIONS];

	const events = $derived([
		{ value: '', label: 'Any event' },
		...types.map((type) => ({ value: type.name, label: type.name }))
	]);
</script>

<div class="flex flex-wrap items-end gap-x-6 gap-y-3">
	<FilterGroup label="Status">
		<FilterSelect
			label="Status"
			labelled={false}
			value={status}
			options={statuses}
			onselect={(next) =>
				// eslint-disable-next-line svelte/no-navigation-without-resolve -- hrefFor resolves
				goto(hrefFor({ status: next || null }), { noScroll: true })}
		/>
	</FilterGroup>

	<FilterGroup label="Event">
		<FilterSelect
			label="Event"
			labelled={false}
			value={eventType}
			options={events}
			onselect={(next) =>
				// eslint-disable-next-line svelte/no-navigation-without-resolve -- hrefFor resolves
				goto(hrefFor({ type: next || null }), { noScroll: true })}
		/>
	</FilterGroup>
</div>
