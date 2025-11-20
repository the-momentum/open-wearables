# Open Wearables Platform - Frontend

Modern web application built with TanStack Start for the Open Wearables Platform - a unified API for health data aggregation and automation.

## Tech Stack

- **Framework**: TanStack Start (React 19)
- **Language**: TypeScript 5.7
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
│   └── features/        # Feature-specific components
├── routes/
│   ├── __root.tsx       # Root layout with providers
│   ├── index.tsx        # Home (redirects to /login)
│   ├── login.tsx        # Login page
│   └── _authenticated/  # Protected routes
│       ├── dashboard.tsx
│       └── users.tsx
├── lib/
│   └── utils.ts         # Utility functions
├── hooks/               # Custom React hooks
└── styles.css           # Global styles and design tokens
```

## Getting Started

### Prerequisites

- Node.js 18+
- npm or pnpm

### Installation

1. Clone the repository
2. Install dependencies:

```bash
npm install
```

3. Copy environment variables:

```bash
cp .env.example .env
```

4. Start the development server:

```bash
npm run dev
```

The app will be available at http://localhost:3000

## Available Scripts

- `npm run dev` - Start development server on port 3000
- `npm run build` - Build for production
- `npm run serve` - Preview production build
- `npm test` - Run tests with Vitest

## Environment Variables

Create a `.env` file based on `.env.example`:

```bash
VITE_API_URL=http://localhost:8000  # Backend API URL
```

## Design System

### Colors

The application uses a custom color palette defined in `src/styles.css`:

- **Primary**: Blue (#3B82F6) - Main brand color
- **Secondary**: Teal (#14B8A6) - Accent color
- **Success**: Green - Success states
- **Warning**: Orange - Warning states
- **Destructive**: Red - Error states

### Dark Mode

Dark mode is enabled by default using the `dark` class on the root HTML element.

## Routing

TanStack Start uses file-based routing:

- `/` - Redirects to `/login`
- `/login` - Authentication page
- `/_authenticated/*` - Protected routes (requires authentication)
  - `/dashboard` - Main dashboard
  - `/users` - User management
  - `/health-insights` - Health automations
  - `/credentials` - API credentials

## Components

### UI Components (shadcn/ui)

Installed components:

- Button
- Card
- Input
- Label
- Form
- Select
- Textarea
- Badge
- Avatar
- Separator
- Sonner (Toast)
- Table
- Dropdown Menu
- Dialog
- Sheet
- Sidebar

To add more components:

```bash
npx shadcn@latest add [component-name]
```

### Layout Components

- **AppSidebar**: Main navigation sidebar
- **AuthenticatedLayout**: Layout wrapper for protected routes

## State Management

- **TanStack Query**: Server state management and caching
- **React Context**: For global UI state (theme, sidebar)
- **React Hook Form**: Form state management

## API Integration

API calls should be made using TanStack Query for optimal caching and state management:

```typescript
import { useQuery } from '@tanstack/react-query';

function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/users`);
      return response.json();
    },
  });
}
```

## Authentication

Authentication is scaffolded but needs to be connected to the backend:

1. Update `/src/routes/login.tsx` to call the actual auth API
2. Implement session management
3. Add route protection in `/_authenticated` layout

## Testing

Tests are set up with Vitest and React Testing Library:

```bash
npm test
```

## Building for Production

```bash
npm run build
```

This creates an optimized production build in the `dist/` directory.

## Deployment

The application can be deployed to:

- Vercel
- Netlify
- Cloudflare Pages
- Any Node.js hosting platform

Set the build command to `npm run build` and the output directory to `dist`.

## Contributing

1. Create a feature branch
2. Make your changes
3. Write/update tests
4. Submit a pull request

## Code Style

- Use TypeScript strict mode
- Follow ESLint rules
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
