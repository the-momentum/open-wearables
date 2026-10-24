<script lang="ts">
	import Download from '@lucide/svelte/icons/download';
	import Mail from '@lucide/svelte/icons/mail';
	import { enhance } from '$app/forms';
	import { resolve } from '$app/paths';
	import { publicApiUrl } from '$lib/config/public-api';
	import SeatUsage from '$lib/components/mobile-app/SeatUsage.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import CopyField from '$lib/components/ui/CopyField.svelte';
	import Sheet from '$lib/components/ui/Sheet.svelte';
	import TextField from '$lib/components/ui/TextField.svelte';
	import type { AppEntitlement } from '$lib/server/app-registration';
	import type { InvitationCode } from '$lib/server/invitations';
	import type { User } from '$lib/users/types';
	import { formatDateTime } from '$lib/utils/datetime';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';

	let {
		open = $bindable(false),
		user,
		invitation,
		appEnabled,
		seats,
		sentTo,
		emailMessage
	}: {
		open?: boolean;
		user: User;
		invitation: InvitationCode | null;
		appEnabled: boolean;
		seats: AppEntitlement | null;
		sentTo?: string;
		emailMessage?: string;
	} = $props();

	const apiUrl = publicApiUrl();
	const server = $derived(apiUrl ? new URL(apiUrl).host : '');
	const displayCode = $derived(
		invitation ? `${invitation.code.slice(0, 4)}-${invitation.code.slice(4)}` : ''
	);
	const submit = createSubmitFlag();
	// As an image, not inline markup: the SVG then cannot run anything in the page.
	const qrSrc = $derived(
		invitation ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(invitation.qr_svg)}` : ''
	);
	let email = $derived(user.email ?? '');

	function save(blob: Blob, name: string) {
		const url = URL.createObjectURL(blob);
		const link = Object.assign(document.createElement('a'), { href: url, download: name });
		link.click();
		URL.revokeObjectURL(url);
	}

	const downloadSvg = () =>
		invitation &&
		save(new Blob([invitation.qr_svg], { type: 'image/svg+xml' }), 'invitation-qr.svg');

	/** Rasterises the instance's SVG, so the PNG matches what the dialog shows. */
	async function downloadPng() {
		if (!invitation) return;
		const image = new Image();
		image.src = qrSrc;
		await image.decode();
		const canvas = Object.assign(document.createElement('canvas'), { width: 1024, height: 1024 });
		const context = canvas.getContext('2d');
		if (!context) return;
		context.imageSmoothingEnabled = false;
		context.fillStyle = '#fff';
		context.fillRect(0, 0, canvas.width, canvas.height);
		context.drawImage(image, 0, 0, canvas.width, canvas.height);
		canvas.toBlob((blob) => blob && save(blob, 'invitation-qr.png'), 'image/png');
	}
</script>

<Sheet bind:open title="Connect mobile app">
	<div class="flex flex-col gap-5 px-4 pb-2">
		{#if appEnabled && invitation}
			<p class="text-sm text-muted-foreground">
				Scan with the phone camera or open the link on the phone. The Open Wearables Connect app
				opens with everything filled in. The invitation works once and replaces any earlier one.
			</p>

			<div class="flex flex-col items-center gap-3">
				<img
					src={qrSrc}
					alt="QR code of the invitation link"
					class="size-52 rounded-lg border border-border bg-white p-2 [image-rendering:pixelated]"
				/>
				<div class="flex gap-2">
					<Button variant="outline" size="sm" onclick={downloadPng}>
						<Download size={14} aria-hidden="true" /> PNG
					</Button>
					<Button variant="outline" size="sm" onclick={downloadSvg}>
						<Download size={14} aria-hidden="true" /> SVG
					</Button>
				</div>
			</div>

			<CopyField label="Invitation link" value={invitation.invite_url} />

			<form
				method="POST"
				action="?/emailInvite"
				class="flex flex-col gap-2"
				use:enhance={submit.enhance}
			>
				<div class="flex items-end gap-2">
					<div class="min-w-0 flex-1">
						<TextField
							name="email"
							label="Send by email"
							type="email"
							placeholder="name@example.com"
							bind:value={email}
						/>
					</div>
					<Button type="submit" variant="outline" disabled={submit.submitting || !email}>
						<Mail size={14} aria-hidden="true" />
						{submit.submitting ? 'Sending…' : 'Send'}
					</Button>
				</div>
				{#if emailMessage}
					<Alert>{emailMessage}</Alert>
				{:else if sentTo}
					<p class="text-xs text-success" role="status">Sent to {sentTo}.</p>
				{/if}
			</form>

			{#if seats}
				<SeatUsage entitlement={seats} />
			{/if}
		{:else if !appEnabled}
			<Alert tone="warning">
				The Open Wearables Connect app is not enabled for this instance, so it cannot connect people
				yet.
				<a class="font-medium underline" href={resolve('/settings/mobile-app')}
					>Register in Settings</a
				>
			</Alert>
		{/if}

		{#if invitation}
			<details class="text-sm" open={!appEnabled}>
				<summary class="cursor-pointer font-medium">Enter manually</summary>
				<div class="mt-3 flex flex-col gap-3">
					{#if apiUrl}
						<CopyField label="Server" value={server} />
					{:else}
						<Alert
							>No VITE_API_URL is configured, so the address a device should dial is unknown.</Alert
						>
					{/if}
					<CopyField label="Invitation code" value={displayCode} mono />
					<p class="text-xs text-muted-foreground">
						Expires {formatDateTime(invitation.expires_at)}
					</p>
				</div>
			</details>
		{/if}
	</div>
</Sheet>
