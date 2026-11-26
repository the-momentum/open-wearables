<script lang="ts">
	import { enhance } from '$app/forms';
	import { resolve } from '$app/paths';
	import LogOut from '@lucide/svelte/icons/log-out';
	import { ICON } from '$lib/components/ui/icon';
	import { cn } from '$lib/utils/cn';
	import { NAV_ITEM, NAV_ITEM_IDLE } from './navItem';
</script>

<!-- A form, not a click handler: only the server can clear an HttpOnly cookie. -->
<form method="POST" action={resolve('/logout')} use:enhance class="contents">
	<button type="submit" class={cn(NAV_ITEM, NAV_ITEM_IDLE, 'w-full hover:text-danger')}>
		<LogOut size={ICON.md} aria-hidden="true" class="shrink-0" />
		Logout
	</button>
</form>
