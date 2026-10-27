<script lang="ts">
	import Building2 from '@lucide/svelte/icons/building-2';
	import Scale from '@lucide/svelte/icons/scale';
	import { enhance } from '$app/forms';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import SwitchField from '$lib/components/ui/SwitchField.svelte';
	import TextField from '$lib/components/ui/TextField.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import { createSubmitFlag, messageFrom } from '$lib/utils/forms.svelte';
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	const submit = createSubmitFlag();
	const legalSubmit = createSubmitFlag();

	// Writable deriveds: edited freely, reset to the saved values when the page data reloads.
	let name = $derived(data.settings.organization_name ?? '');
	let logoUrl = $derived(data.settings.logo_url ?? '');
	let supportEmail = $derived(data.settings.support_email ?? '');

	let privacyPolicyUrl = $derived(data.settings.privacy_policy_url ?? '');
	let termsUrl = $derived(data.settings.terms_url ?? '');
	let requireAcceptance = $derived(data.settings.require_acceptance);
	const hasDocuments = $derived(Boolean(privacyPolicyUrl.trim() || termsUrl.trim()));

	const message = $derived(messageFrom(form, 'save'));
	const saved = $derived(form?.action === 'save' && 'saved' in form);
	const legalMessage = $derived(
		messageFrom(form, 'saveLegal') ?? messageFrom(form, 'publishLegal')
	);
	const legalSaved = $derived(
		(form?.action === 'saveLegal' || form?.action === 'publishLegal') && 'saved' in form
	);
</script>

<Card
	icon={Building2}
	title="Organisation"
	description="How this instance introduces itself to the people who share data with it, for example in the Open Wearables Connect app before they connect."
>
	<form method="POST" action="?/save" class="flex flex-col gap-4" use:enhance={submit.enhance}>
		{#if message}
			<Alert>{message}</Alert>
		{/if}

		<TextField
			name="organization_name"
			label="Organisation name"
			placeholder="Acme Health"
			maxlength={100}
			bind:value={name}
		/>
		<TextField
			name="logo_url"
			label="Logo URL"
			hint="An https address of a square image. Leave empty to show the name only."
			placeholder="https://acmehealth.com/logo.png"
			type="url"
			bind:value={logoUrl}
		/>
		<TextField
			name="support_email"
			label="Support email"
			hint="Where users are told to write when they cannot connect."
			placeholder="help@acmehealth.com"
			type="email"
			bind:value={supportEmail}
		/>

		<div class="flex items-center justify-end gap-3">
			{#if saved && !submit.submitting}<span class={MICRO} role="status">Saved</span>{/if}
			<Button type="submit" disabled={submit.submitting}>
				{submit.submitting ? 'Saving…' : 'Save'}
			</Button>
		</div>
	</form>
</Card>

<Card
	icon={Scale}
	title="Legal documents"
	description="Shown in the Open Wearables Connect app before a user connects. An organisation that collects other people's health data (a clinic, a coach) should link its own privacy policy, and terms if it has them. A self-hosted instance used only by you does not need to."
	class="mt-6"
>
	<form
		method="POST"
		action="?/saveLegal"
		class="flex flex-col gap-4"
		use:enhance={legalSubmit.enhance}
	>
		{#if legalMessage}
			<Alert>{legalMessage}</Alert>
		{/if}

		<TextField
			name="privacy_policy_url"
			label="Privacy policy URL"
			hint="An https address of your privacy policy for the people who share data with you."
			placeholder="https://acmehealth.com/privacy"
			type="url"
			bind:value={privacyPolicyUrl}
		/>
		<TextField
			name="terms_url"
			label="Terms URL"
			hint="Optional terms of use."
			placeholder="https://acmehealth.com/terms"
			type="url"
			bind:value={termsUrl}
		/>
		<input
			type="hidden"
			name="require_acceptance"
			value={String(requireAcceptance && hasDocuments)}
		/>
		{#if hasDocuments}
			<SwitchField
				label="Require users to accept these documents before connecting"
				bind:checked={requireAcceptance}
			/>
		{/if}
		<p class={MICRO}>
			Version {data.settings.legal_documents_version}. Changing a URL publishes a new version; when
			the text behind the same URL changes, publish one by hand. Users who must accept the documents
			are asked again in the app the next time they open it.
		</p>

		<div class="flex flex-wrap items-center justify-end gap-3">
			{#if legalSaved && !legalSubmit.submitting}<span class={MICRO} role="status">Saved</span>{/if}
			{#if data.settings.privacy_policy_url || data.settings.terms_url}
				<Button
					type="submit"
					variant="outline"
					formaction="?/publishLegal"
					disabled={legalSubmit.submitting}
				>
					Publish new version
				</Button>
			{/if}
			<Button type="submit" disabled={legalSubmit.submitting}>
				{legalSubmit.submitting ? 'Saving…' : 'Save'}
			</Button>
		</div>
	</form>
</Card>
