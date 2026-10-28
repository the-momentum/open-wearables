import { describe, expect, it } from 'vitest';
import { problemMessage } from './api';

describe('problemMessage', () => {
	it('shows the first validation failure without the field path', () => {
		const body = {
			status: 422,
			detail: 'body.user_id: Input should be a valid UUID (and 1 more)',
			code: 'VALIDATION_ERROR',
			errors: [
				{ loc: ['body', 'user_id'], msg: 'Input should be a valid UUID', type: 'uuid_parsing' },
				{ loc: ['body', 'url'], msg: 'Field required', type: 'missing' }
			]
		};
		expect(problemMessage(body)).toBe('Input should be a valid UUID');
	});

	it('shows the detail of any other error', () => {
		expect(problemMessage({ status: 409, detail: 'User exists.', code: 'CONFLICT' })).toBe(
			'User exists.'
		);
	});

	it('has nothing to show for a body that is not a problem', () => {
		expect(problemMessage(null)).toBeUndefined();
		expect(problemMessage({ detail: [{ msg: 'x' }] })).toBeUndefined();
		expect(problemMessage({ detail: 'Bad', errors: [] })).toBe('Bad');
	});
});
