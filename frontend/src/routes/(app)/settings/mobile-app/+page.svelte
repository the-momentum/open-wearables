<script lang="ts">
	import Smartphone from '@lucide/svelte/icons/smartphone';
	import MailCheck from '@lucide/svelte/icons/mail-check';
	import { enhance } from '$app/forms';
	import { invalidateAll } from '$app/navigation';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import ConfirmDialog from '$lib/components/ui/ConfirmDialog.svelte';
	import CopyableId from '$lib/components/ui/CopyableId.svelte';
	import TextField from '$lib/components/ui/TextField.svelte';
	import { MICRO } from '$lib/components/ui/typography';
	import SeatUsage from '$lib/components/mobile-app/SeatUsage.svelte';
	import { formatDateTime } from '$lib/utils/datetime';
	import { createSubmitFlag, messageFrom } from '$lib/utils/forms.svelte';
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	const submit = createSubmitFlag();
	let unregistering = $state(false);

	const registration = $derived(data.registration);
	const pending = $derived(registration.status === 'pending_verification');
	const active = $derived(registration.status === 'active');

	let adminEmail = $derived(registration.admin_email ?? data.developerEmail);
	let acceptTerms = $state(false);
	let marketingConsent = $state(false);

	const registerMessage = $derived(messageFrom(form, 'register'));
	const unregisterMessage = $derived(messageFrom(form, 'unregister'));

	// The admin clicks the link in their email in another tab: keep asking until it lands.
	$effect(() => {
		if (!pending) return;
		const timer = setInterval(() => invalidateAll(), 5000);
		return () => clearInterval(timer);
	});
</script>

<Card
	icon={Smartphone}
	title="Mobile app"
	description="Let the people you invite connect with the Open Wearables Connect app from the App Store and Google Play. Registering sends licenses.openwearables.io a random instance id, a public key and the email below - never this server's address or any user data."
>
	{#if active}
		<div class="flex flex-col gap-4">
			<div class="flex flex-wrap items-center gap-2">
				<Badge tone="success">App enabled</Badge>
				<span class={MICRO}
					>Registered {registration.registered_at
						? formatDateTime(registration.registered_at)
						: ''}</span
				>
			</div>
			{#if data.entitlement}
				<SeatUsage entitlement={data.entitlement} />
			{:else}
				<Alert tone="warning"
					>Seat usage is unavailable: the license server could not be reached.</Alert
				>
			{/if}
			<dl class="grid gap-3 text-sm sm:grid-cols-2">
				<div>
					<dt class="text-muted-foreground">Admin email</dt>
					<dd>{registration.admin_email}</dd>
				</div>
				<div>
					<dt class="text-muted-foreground">Instance id</dt>
					<dd><CopyableId value={registration.instance_id ?? ''} /></dd>
				</div>
			</dl>
			{#if unregisterMessage}<Alert>{unregisterMessage}</Alert>{/if}
			<div class="flex justify-end">
				<Button variant="outline" class="text-danger" onclick={() => (unregistering = true)}
					>Unregister</Button
				>
			</div>
		</div>
	{:else}
		<form
			method="POST"
			action="?/register"
			class="flex flex-col gap-4"
			use:enhance={submit.enhance}
		>
			{#if registerMessage}<Alert>{registerMessage}</Alert>{/if}
			{#if pending}
				<div
					class="flex items-start gap-3 rounded-lg border border-border bg-surface-muted p-3 text-sm"
				>
					<MailCheck size={18} class="mt-0.5 shrink-0" aria-hidden="true" />
					<p>
						Check <strong>{registration.admin_email}</strong> and click the confirmation link. This page
						updates by itself once it is confirmed. No email? Check spam, or send it again.
					</p>
				</div>
			{:else if registration.status === 'removed'}
				<Alert tone="warning"
					>The license server no longer knows this instance. Register it again.</Alert
				>
			{/if}

			<TextField
				name="admin_email"
				label="Admin email"
				hint="Gets the confirmation link and service messages about the app, such as reaching the seat limit."
				type="email"
				required
				bind:value={adminEmail}
			/>
			<label class="flex items-start gap-2.5 text-sm">
				<input
					type="checkbox"
					name="accept_terms"
					required
					bind:checked={acceptTerms}
					class="mt-0.5 size-4"
				/>
				<span>
					I accept the Open Wearables Connect free plan terms (up to 5 connected people) and the
					privacy notice.
				</span>
			</label>
			<label class="flex items-start gap-2.5 text-sm text-secondary-foreground">
				<input
					type="checkbox"
					name="marketing_consent"
					bind:checked={marketingConsent}
					class="mt-0.5 size-4"
				/>
				<span>Email me about new features and paid plans (optional).</span>
			</label>

			<div class="flex justify-end">
				<Button type="submit" disabled={submit.submitting || !acceptTerms}>
					{submit.submitting ? 'Sending…' : pending ? 'Send the link again' : 'Register instance'}
				</Button>
			</div>
		</form>
	{/if}
</Card>

<ConfirmDialog
	bind:open={unregistering}
	title="Unregister this instance?"
	action="?/unregister"
	confirmLabel="Unregister"
	busyLabel="Unregistering…"
	destructive
	message={unregisterMessage}
>
	<p class="text-sm text-muted-foreground">
		Every phone connected through the Open Wearables Connect app stops syncing and its seat is
		released. The SDK and API keep working. You can register again later.
	</p>
</ConfirmDialog>
