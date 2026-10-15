/** A click anywhere on the card toggles it, except on its own controls or to end a text selection. */
export function togglesCard(event: MouseEvent): boolean {
	const target = event.target as Element | null;
	const control = target?.closest('a, button, input, select, textarea, label');

	if (control && !control.matches('[data-accordion-toggle]')) return false;
	return !document.getSelection()?.toString();
}
