<script lang="ts">
	import UserPlus from '@lucide/svelte/icons/user-plus';
	import Button from '$lib/components/ui/Button.svelte';

	let { onclick }: { onclick: () => void } = $props();
</script>

<Button {onclick} class="w-full">
	<UserPlus size={16} aria-hidden="true" />
	Add user
</Button>
