<script lang="ts">
	import HardDrive from '@lucide/svelte/icons/hard-drive';
	import LifecycleForm from '$lib/components/lifecycle/LifecycleForm.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import EmptyState from '$lib/components/ui/EmptyState.svelte';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import { messageFrom } from '$lib/utils/forms.svelte';
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	const dispatched = $derived(form?.action === 'run' && 'dispatched' in form);
</script>

<div class="flex flex-col gap-5">
	{#if messageFrom(form, 'save')}
		<Alert>{messageFrom(form, 'save')}</Alert>
	{/if}

	{#await data.lifecycle}
		<!-- Roughly the shape of what is coming, so nothing jumps when it lands. -->
		<Skeleton class="h-40" />
		<Skeleton class="h-72" />
		<div class="grid gap-5 lg:grid-cols-2">
			<Skeleton class="h-32" />
			<Skeleton class="h-32" />
		</div>
	{:then lifecycle}
		<LifecycleForm {lifecycle} message={messageFrom(form, 'run')} {dispatched} />
	{:catch}
		<Card>
			<EmptyState
				icon={HardDrive}
				title="Could not read the storage estimate"
				description="The backend did not answer in time. On a large database the estimate scans the series table, which can take a while — try again in a moment."
			/>
		</Card>
	{/await}
</div>
