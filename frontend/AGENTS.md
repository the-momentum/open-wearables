# Frontend Development Guide

This file extends the root AGENTS.md with frontend-specific patterns.

## Tech Stack
- React 19 + TypeScript
- TanStack Router for file-based routing
- TanStack Query for server state
- React Hook Form + Zod for forms
- Tailwind CSS 4.0 + shadcn/ui for styling
- Sonner for toast notifications
- Lucide React for icons
- Vitest for testing

### Resources
- [TanStack Start Documentation](https://tanstack.com/start)
- [TanStack Router Documentation](https://tanstack.com/router)
- [TanStack Query Documentation](https://tanstack.com/query)
- [shadcn/ui Documentation](https://ui.shadcn.com)
- [Tailwind CSS Documentation](https://tailwindcss.com)

## Project Structure
```
src/
├── routes/              # TanStack Router pages (file-based)
│   ├── __root.tsx       # Root layout with providers
│   ├── _authenticated.tsx  # Protected route guard
│   └── _authenticated/  # Protected pages
├── components/
│   ├── ui/              # shadcn/ui components
│   ├── common/          # Shared components (LoadingSpinner, ErrorState)
│   └── [feature]/       # Feature components (user/, settings/)
├── hooks/
│   ├── api/             # React Query hooks (use-users.ts, use-health.ts)
│   └── use-*.ts         # Custom hooks (use-auth.ts, use-mobile.ts)
├── lib/
│   ├── api/
│   │   ├── client.ts    # API client with retry logic
│   │   ├── config.ts    # Base URL, endpoints
│   │   ├── types.ts     # API types
│   │   └── services/    # Service modules
│   ├── auth/session.ts  # Session management (localStorage)
│   ├── constants/
│   │   └── routes.ts    # Centralized route paths and redirects
│   ├── query/keys.ts    # Query key factory
│   ├── validation/      # Zod schemas
│   └── errors/          # Error handling
└── styles.css           # Tailwind + CSS variables
```

## Reusable Components

### common/

| Component | Description |
|-----------|-------------|
| `LoadingSpinner` | Animated spinner with size variants (`sm`, `md`, `lg`) |
| `LoadingState` | Full-page loading with spinner and optional message |
| `ErrorState` | Error display with message and optional retry button |
| `MetricCard` | Statistics card with icon, value, label, and selection state |
| `SectionHeader` | Section title with optional date range selector |
| `CursorPagination` | Previous/next navigation for cursor-based pagination |

### layout/

| Component | Description |
|-----------|-------------|
| `SimpleSidebar` | Navigation sidebar with menu items and logout button |

### login/

| Component | Description |
|-----------|-------------|
| `CodePreviewCard` | Decorative code editor preview for login/register pages |

### pages/dashboard/

| Component | Description |
|-----------|-------------|
| `StatsCard` | Dashboard stat with value, icon, and growth percentage indicator |
| `StatsGrid` | Responsive grid layout for StatsCard instances |
| `DashboardLoadingState` | Skeleton loading state for dashboard |
| `DashboardErrorState` | Error state with retry button for dashboard |
| `DataSummaryCard` | Summary card showing count and label |
| `DataMetricsSection` | Displays top series and workout types |
| `RecentUsersSection` | Recent users list with status badges |

### settings/providers/

| Component | Description |
|-----------|-------------|
| `ProviderItem` | Wearable provider row with connection toggle switch |

### user/

| Component | Description |
|-----------|-------------|
| `ProfileSection` | User profile header with edit dialog and connected providers list |
| `BodySection` | Body metrics display with period toggle (7d/30d/90d) |
| `SleepSection` | Sleep data with charts and session details |
| `ActivitySection` | Activity metrics with dynamic chart selection |
| `WorkoutSection` | Workout list with heart rate time series chart |
| `ConnectionCard` | Provider connection status with sync button |

### users/

| Component | Description |
|-----------|-------------|
| `UsersTable` | Data table with sorting, search, pagination, and row actions |

## Common Patterns

### Creating API Hooks (React Query)

```typescript
// src/hooks/api/use-users.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { usersService } from '../../lib/api';
import { queryKeys } from '../../lib/query/keys';

// Simple query
export function useUsers(filters?: { search?: string }) {
  return useQuery({
    queryKey: queryKeys.users.list(filters),
    queryFn: () => usersService.getAll(filters),
  });
}

// Query with conditional fetching
export function useUser(id: string) {
  return useQuery({
    queryKey: queryKeys.users.detail(id),
    queryFn: () => usersService.getById(id),
    enabled: !!id,
  });
}

// Mutation with optimistic updates
export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UserUpdate }) =>
      usersService.update(id, data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.users.detail(id) });
      const previousUser = queryClient.getQueryData<UserRead>(
        queryKeys.users.detail(id)
      );
      // Optimistically update cache
      if (previousUser) {
        queryClient.setQueryData(queryKeys.users.detail(id), {
          ...previousUser,
          ...data,
        });
      }
      return { previousUser };
    },
    onSuccess: (updatedUser, { id }) => {
      queryClient.setQueryData(queryKeys.users.detail(id), updatedUser);
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });
      toast.success('User updated successfully');
    },
    onError: (error, { id }, context) => {
      // Rollback on error
      if (context?.previousUser) {
        queryClient.setQueryData(queryKeys.users.detail(id), context.previousUser);
      }
      toast.error(error instanceof Error ? error.message : 'Failed to update');
    },
  });
}
```

### Query Keys Factory

```typescript
// src/lib/query/keys.ts
export const queryKeys = {
  users: {
    all: ['users'] as const,
    lists: () => [...queryKeys.users.all, 'list'] as const,
    list: (filters?: { search?: string }) =>
      [...queryKeys.users.lists(), filters] as const,
    details: () => [...queryKeys.users.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.users.details(), id] as const,
  },
  health: {
    all: ['health'] as const,
    connections: (userId: string) =>
      [...queryKeys.health.all, 'connections', userId] as const,
    heartRate: (userId: string, deviceId: string, days: number) =>
      [...queryKeys.health.all, 'heartRate', userId, deviceId, days] as const,
  },
};
```

### Route Constants

All frontend route paths are centralized in `src/lib/constants/routes.ts`. **Never hardcode route paths** - always import from this file.

```typescript
// src/lib/constants/routes.ts
export const ROUTES = {
  // Public routes
  login: '/login',
  register: '/register',
  forgotPassword: '/forgot-password',
  resetPassword: '/reset-password',
  acceptInvite: '/accept-invite',

  // Authenticated routes
  dashboard: '/dashboard',
  users: '/users',
  settings: '/settings',

  // Widget routes
  widgetConnect: '/widget/connect',
} as const;

export const DEFAULT_REDIRECTS = {
  authenticated: ROUTES.dashboard,
  unauthenticated: ROUTES.login,
} as const;
```

**Usage examples:**

```typescript
// For redirects (use DEFAULT_REDIRECTS)
import { DEFAULT_REDIRECTS } from '@/lib/constants/routes';

navigate({ to: DEFAULT_REDIRECTS.authenticated });
throw redirect({ to: DEFAULT_REDIRECTS.unauthenticated });

// For links and navigation (use ROUTES)
import { ROUTES } from '@/lib/constants/routes';

<Link to={ROUTES.login}>Sign in</Link>
navigate({ to: ROUTES.users });
```

### Zod Validation Schemas

```typescript
// src/lib/validation/auth.schemas.ts
import { z } from 'zod';

export const emailSchema = z
  .string()
  .min(1, 'Email is required')
  .email('Please enter a valid email address');

export const passwordSchema = z
  .string()
  .min(8, 'Password must be at least 8 characters')
  .refine(
    (val) => /[A-Z]/.test(val) && /[a-z]/.test(val) || /[0-9]/.test(val),
    { message: 'Password must contain mixed case or a number' }
  );

export const registerSchema = z
  .object({
    email: emailSchema,
    password: passwordSchema,
    confirmPassword: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  });

export type RegisterFormData = z.infer<typeof registerSchema>;
```

### Forms with React Hook Form

```typescript
// In a route or component
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { registerSchema, type RegisterFormData } from '@/lib/validation/auth.schemas';

function RegisterPage() {
  const form = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: { email: '', password: '', confirmPassword: '' },
  });

  const onSubmit = (data: RegisterFormData) => {
    // Handle submission
  };

  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <Input {...form.register('email')} placeholder="Email" />
      {form.formState.errors.email && (
        <p className="text-xs text-red-500">
          {form.formState.errors.email.message}
        </p>
      )}
      <Button type="submit">Register</Button>
    </form>
  );
}
```

### Protected Routes

```typescript
// src/routes/_authenticated.tsx
import { createFileRoute, Outlet, redirect } from '@tanstack/react-router';
import { isAuthenticated } from '@/lib/auth/session';
import { DEFAULT_REDIRECTS } from '@/lib/constants/routes';

export const Route = createFileRoute('/_authenticated')({
  component: AuthenticatedLayout,
  beforeLoad: () => {
    // Skip during SSR (localStorage not available)
    if (typeof window === 'undefined') return;
    if (!isAuthenticated()) {
      throw redirect({ to: DEFAULT_REDIRECTS.unauthenticated });
    }
  },
});

function AuthenticatedLayout() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
```

### API Endpoints

All API endpoint paths in `src/lib/api/config.ts` **must end with a trailing slash** for collection endpoints (e.g., `/api/v1/developers/`, `/api/v1/invitations/`). FastAPI redirects non-trailing-slash requests with a 307, which causes mixed content errors behind HTTPS reverse proxies.

```typescript
// CORRECT
developers: '/api/v1/developers/',
invitations: '/api/v1/invitations/',

// WRONG - causes 307 redirect → mixed content on HTTPS
developers: '/api/v1/developers',
invitations: '/api/v1/invitations',
```

### API Client

```typescript
// src/lib/api/client.ts
import { ROUTES } from '../constants/routes';

export const apiClient = {
  async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const url = `${API_CONFIG.baseUrl}${endpoint}`;
    const token = getToken();

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
    };

    const response = await fetchWithRetry(url, { ...options, headers });

    if (response.status === 401) {
      clearSession();
      window.location.href = ROUTES.login;
    }

    if (!response.ok) {
      throw ApiError.fromResponse(response);
    }

    return response.json();
  },

  get<T>(endpoint: string) { return this.request<T>(endpoint, { method: 'GET' }); },
  post<T>(endpoint: string, body: unknown) {
    return this.request<T>(endpoint, { method: 'POST', body: JSON.stringify(body) });
  },
  patch<T>(endpoint: string, body: unknown) {
    return this.request<T>(endpoint, { method: 'PATCH', body: JSON.stringify(body) });
  },
  delete<T>(endpoint: string) { return this.request<T>(endpoint, { method: 'DELETE' }); },
};
```

### Toast Notifications

```typescript
import { toast } from 'sonner';

// Success
toast.success('User created successfully');

// Error
toast.error('Failed to save changes');

// With action
toast.success('Copied to clipboard');

// In mutations (common pattern)
onSuccess: () => {
  queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });
  toast.success('Operation completed');
},
onError: (error) => {
  toast.error(error instanceof Error ? error.message : 'Operation failed');
},
```

## Adding shadcn/ui Components

```bash
pnpm dlx shadcn@latest add button
pnpm dlx shadcn@latest add card
pnpm dlx shadcn@latest add input
```

Components are installed to `src/components/ui/`.

## Code Style
- Line width: 80 characters
- Single quotes, semicolons always
- 2-space indentation
- TypeScript strict mode
- Use `cn()` utility for conditional Tailwind classes

```typescript
import { cn } from '@/lib/utils';

<div className={cn('base-class', isActive && 'active-class')} />
```

## Environment Variables

Access via `import.meta.env`:

```typescript
// src/lib/api/config.ts
export const API_CONFIG = {
  baseUrl: import.meta.env.VITE_API_URL || 'http://localhost:8000',
};
```

## Testing
- Framework: Vitest + React Testing Library
- Run: `pnpm run test`
- Test files: `*.test.ts`, `*.test.tsx`

## Commands

```bash
pnpm run dev          # Start dev server (port 3000)
pnpm run build        # Production build
pnpm run lint         # Run oxlint
pnpm run lint:fix     # Fix linting issues
pnpm run format       # Format with Prettier
pnpm run format:check # Check formatting
pnpm run test         # Run tests
```

Run `pnpm run lint:fix && pnpm run format` after making changes.
