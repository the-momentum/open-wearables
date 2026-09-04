<script lang="ts">
	import { enhance } from '$app/forms';
	import { resolve } from '$app/paths';
	import LogOut from '@lucide/svelte/icons/log-out';
</script>

<!-- A form, not a click handler: only the server can clear an HttpOnly cookie. -->
<form method="POST" action={resolve('/logout')} use:enhance class="contents">
	<button
		type="submit"
		class="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-sm font-medium
			text-muted-foreground transition-colors hover:bg-surface-muted hover:text-danger"
	>
		<LogOut size={18} aria-hidden="true" />
		Logout
	</button>
</form>
