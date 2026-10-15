<script lang="ts">
	import ApiEndpoint from '$lib/components/settings/credentials/ApiEndpoint.svelte';
	import ApiKeys from '$lib/components/settings/credentials/ApiKeys.svelte';
	import Applications from '$lib/components/settings/credentials/Applications.svelte';
	import type { ActionData, PageData } from './$types';
	import { messageFrom } from '$lib/utils/forms.svelte';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	const messageFor = (action: string) => messageFrom(form, action);

	// Which action produced it decides which section reveals it; only the four
	// that mint one carry the field at all.
	const secretFrom = (actions: string[]) =>
		form && 'secret' in form && actions.includes(form.action) ? form.secret : undefined;
</script>

<div class="flex flex-col gap-5">
	<ApiEndpoint />

	<ApiKeys keys={data.keys} {messageFor} secret={secretFrom(['createKey', 'rotateKey'])} />

	<Applications
		applications={data.applications}
		{messageFor}
		secret={secretFrom(['createApp', 'rotateApp'])}
	/>
</div>
