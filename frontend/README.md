# Open Wearables Platform - Frontend

Modern web application built with TanStack Start for the Open Wearables Platform—a unified API for health data aggregation and automation.

## Tech Stack

- **Framework**: TanStack Start (React 19)
- **Language**: TypeScript 7
- **Styling**: Tailwind CSS 4.0
- **UI Components**: shadcn/ui
- **Data Fetching**: TanStack Query
- **Form Management**: React Hook Form + Zod
- **Charts**: Recharts
- **Icons**: Lucide React

## Features

- File-based routing with TanStack Router
- Server-side rendering (SSR) support
- Type-safe API integration
- Dark mode support
- Responsive design
- Component library with shadcn/ui
- Form validation with Zod
- Toast notifications with Sonner

## Project Structure

```
src/
├── components/
│   ├── ui/              # shadcn/ui components
│   ├── layout/          # Layout components (Sidebar, etc.)
│   ├── common/          # Shared loading, errors, and pagination
│   ├── user/            # User detail sections
│   ├── users/           # User-list components
│   └── webhooks/        # Outgoing webhook components
├── routes/
│   ├── __root.tsx       # Root layout with providers
│   ├── index.tsx        # Home (redirects to /login)
│   ├── login.tsx        # Login page
│   ├── _authenticated.tsx # Protected layout and route guard
│   └── _authenticated/  # Dashboard, users, syncs, and settings
├── lib/                 # API client, auth, query keys, and utilities
├── hooks/               # React Query and application hooks
└── styles.css           # Global styles and design tokens
```

## Getting Started

### Prerequisites

- Node.js 22+
- pnpm

### Installation

1. Clone the repository
2. Install dependencies:

```bash
pnpm install
```

3. Copy environment variables:

```bash
cp .env.example .env
```

4. Start the development server:

```bash
pnpm dev
```

The app will be available at http://localhost:3000

## Available Scripts

- `pnpm dev` - Start development server on port 3000
- `pnpm build` - Build for production
- `pnpm serve` - Preview production build
- `pnpm test` - Run tests with Vitest

## Environment Variables

Create a `.env` file based on `.env.example`:

```bash
VITE_API_URL=http://localhost:8000  # Backend API URL
```

## Design System

### Colors

The application uses a custom color palette defined in `src/styles.css`:

- **Primary**: Electric cyan (`#00E5FF`) — Main brand color
- **Secondary**: Neon magenta (`#FF33AA`) — Secondary actions
- **Accent**: Electric purple (`#9933FF`) — Highlights
- **Success**: Neon green — Success states
- **Warning**: Neon yellow — Warning states
- **Destructive**: Neon red — Error states

### Dark Mode

Dark mode is enabled by default using the `dark` class on the root HTML element.

## Routing

TanStack Start uses file-based routing:

- `/` - Redirects to `/login`
- `/login` - Authentication page
- `/_authenticated/*` - Protected routes (requires authentication)
  - `/dashboard` - Main dashboard
  - `/users` - User management
  - `/webhooks` - Outgoing webhook management
  - `/syncs` - Synchronization status
  - `/coverage` - Provider data coverage
  - `/settings` - Providers, credentials, applications, and account settings

## Components

### UI Components (shadcn/ui)

Installed components:

- Button
- Card
- Input
- Label
- Badge
- Separator
- Sonner (Toast)
- Table
- Dropdown Menu
- Dialog
- Sheet
- Sidebar

To add more components:

```bash
pnpm dlx shadcn@latest add [component-name]
```

### Layout Components

- **SimpleSidebar**: Main navigation sidebar
- **AuthenticatedLayout**: Layout wrapper for protected routes

## State Management

- **TanStack Query**: Server state management and caching
- **React Context**: For global UI state (theme, sidebar)
- **React Hook Form**: Form state management

## API Integration

API calls go through the service layer in `src/lib/api`, wrapped in TanStack Query hooks:

```typescript
import { useQuery } from '@tanstack/react-query';
import { usersService } from '@/lib/api';
import { queryKeys } from '@/lib/query/keys';

function useUsers() {
  return useQuery({
    queryKey: queryKeys.users.list(),
    queryFn: () => usersService.getAll(),
  });
}
```

The services use the shared API client (`src/lib/api/client.ts`), which attaches the auth token, retries `5xx` server errors, and resolves the backend URL at runtime via `resolveApiUrl()` (`src/lib/api/runtime-config.ts`) from the `VITE_API_URL` environment variable. Do not read `import.meta.env.VITE_API_URL` directly in application code—that inlines the value at build time and breaks runtime configuration.

## Authentication

Authentication is implemented: the login page calls the backend auth API through the `useAuth` hook, sessions use bearer tokens attached by the shared API client, and routes under `/_authenticated` are protected by the layout.

## Testing

Tests are set up with Vitest and React Testing Library:

```bash
pnpm test
```

## Building for Production

```bash
pnpm build
```

This produces a Nitro server build in the `.output/` directory. Run it with:

```bash
node .output/server/index.mjs
```

The server listens on port 3000 and serves both the SSR frontend and its static assets.

## Deployment

The frontend is a server-rendered Node.js application, not a static site. Deploy it either as the published Docker image (`themomentum/open-wearables-frontend`) or on any Node.js host running `.output/server/index.mjs`.

The backend API URL is read from the `VITE_API_URL` environment variable at runtime, so the same build works against any backend. See [Deploying with Docker](https://openwearables.io/docs/deployment/docker) for details.

## Contributing

1. Create a feature branch
2. Make your changes
3. Write/update tests
4. Submit a pull request

## Code Style

- Use TypeScript strict mode
- Follow Oxlint rules
- Use Prettier for formatting
- Components should be functional with hooks
- Prefer composition over inheritance

## Resources

- [TanStack Start Documentation](https://tanstack.com/start)
- [TanStack Router Documentation](https://tanstack.com/router)
- [TanStack Query Documentation](https://tanstack.com/query)
- [shadcn/ui Documentation](https://ui.shadcn.com)
- [Tailwind CSS Documentation](https://tailwindcss.com)

## License

See LICENSE file in the root directory.
