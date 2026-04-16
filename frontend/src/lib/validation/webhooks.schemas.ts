import { z } from 'zod';

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const httpsUrl = z
  .string()
  .min(1, 'URL is required')
  .url('Please enter a valid URL')
  .refine((val) => val.startsWith('https://'), {
    message: 'Webhook URL must use HTTPS',
  });

const optionalUuid = z
  .string()
  .trim()
  .optional()
  .refine((val) => !val || uuidPattern.test(val), {
    message: 'Must be a valid UUID',
  });

const filterTypes = z.array(z.string()).optional();

const optionalDescription = z
  .string()
  .max(500, 'Description must be 500 characters or fewer')
  .optional();

export const webhookEndpointFormSchema = z.object({
  url: httpsUrl,
  description: optionalDescription,
  filter_types: filterTypes,
  user_id: optionalUuid,
});

export type WebhookEndpointFormData = z.infer<typeof webhookEndpointFormSchema>;
