<script lang="ts">
	import SeedForm from '$lib/components/seed/SeedForm.svelte';
	import { messageFrom } from '$lib/utils/forms.svelte';
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	const queued = $derived(
		form?.action === 'generate' && 'users' in form && typeof form.users === 'number'
			? { seed: form.seed ?? null, users: form.users }
			: undefined
	);
</script>

<SeedForm
	presets={data.presets}
	sleepProfiles={data.sleepProfiles}
	series={data.series}
	providers={data.providers}
	message={messageFrom(form, 'generate')}
	{queued}
/>
