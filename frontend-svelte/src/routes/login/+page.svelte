<script lang="ts">
	import { enhance } from '$app/forms';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';

	import PublicPage from '$lib/components/layout/PublicPage.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import TextField from '$lib/components/ui/TextField.svelte';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';
	import type { ActionData } from './$types';

	let { form }: { form: ActionData } = $props();

	const submit = createSubmitFlag(undefined, { reset: true });
</script>

<PublicPage title="Sign in" description="Use your Open Wearables developer account.">
	<!-- Works without JS; enhance only avoids the full page reload. -->
	<form method="POST" class="flex flex-col gap-4" use:enhance={submit.enhance}>
		{#if form?.message}
			<Alert>{form.message}</Alert>
		{/if}

		<TextField
			name="email"
			type="email"
			label="Email"
			autocomplete="username"
			required
			value={form?.email ?? ''}
		/>

		<TextField
			name="password"
			type="password"
			label="Password"
			autocomplete="current-password"
			required
		/>

		<Button type="submit" disabled={submit.submitting} class="mt-1 w-full">
			{#if submit.submitting}
				<LoaderCircle size={16} aria-hidden="true" class="animate-spin" />
			{/if}
			{submit.submitting ? 'Signing in…' : 'Sign in'}
		</Button>
	</form>
</PublicPage>
