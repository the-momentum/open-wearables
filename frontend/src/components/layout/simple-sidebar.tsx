import { Link, useLocation } from '@tanstack/react-router';
import {
  Home,
  Users,
  FileText,
  LogOut,
  Settings,
  ExternalLink,
  Webhook,
  RefreshCw,
} from 'lucide-react';
import logotype from '@/logotype.svg';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/use-auth';
import { ROUTES } from '@/lib/constants/routes';
import { Button } from '@/components/ui/button';

const menuItems = [
  {
    title: 'Dashboard',
    url: ROUTES.dashboard,
    icon: Home,
  },
  {
    title: 'Users',
    url: ROUTES.users,
    icon: Users,
  },
  {
    title: 'Webhooks',
    url: ROUTES.webhooks,
    icon: Webhook,
    badge: 'Beta',
  },
  {
    title: 'Syncs',
    url: ROUTES.syncs,
    icon: RefreshCw,
  },
  {
    title: 'Settings',
    url: ROUTES.settings,
    icon: Settings,
  },
  {
    title: 'Documentation',
    url: 'https://openwearables.io/docs',
    icon: FileText,
    external: true,
  },
];

export function SimpleSidebar() {
  const location = useLocation();
  const { logout, isLoggingOut } = useAuth();

  return (
    <aside className="relative w-64 bg-black flex flex-col border-r border-border/40">
      {/* Header */}
      <div className="p-4 border-b border-border/40">
        <img src={logotype} alt="Open Wearables" className="h-auto" />
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        {menuItems.map((item) => {
          const isActive = location.pathname.startsWith(item.url);

          if (item.external) {
            return (
              <a
                key={item.title}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-card/40 hover:text-foreground transition-all duration-200"
              >
                <item.icon className="h-4 w-4 text-muted-foreground" />
                <span>{item.title}</span>
                <ExternalLink className="ml-auto h-3 w-3 text-muted-foreground/70" />
              </a>
            );
          }

          return (
            <Link
              key={item.title}
              to={item.url}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-all duration-200',
                isActive
                  ? 'bg-card text-foreground border-l-2 border-white -ml-[2px] pl-[calc(0.75rem+2px)]'
                  : 'text-muted-foreground hover:bg-card/40 hover:text-foreground'
              )}
            >
              <item.icon
                className={cn(
                  'h-4 w-4 transition-colors',
                  isActive ? 'text-foreground' : 'text-muted-foreground'
                )}
              />
              <span>{item.title}</span>
              {item.badge ? (
                <span className="ml-auto rounded-full border border-[hsl(var(--warning-muted)/0.3)] bg-[hsl(var(--warning-muted)/0.1)] px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[hsl(var(--warning-muted))]">
                  {item.badge}
                </span>
              ) : null}
            </Link>
          );
        })}
      </nav>

      {/* Divider */}
      <div className="mx-3 border-t border-border/40" />

      {/* Footer */}
      <div className="p-3">
        <Button
          variant="ghost"
          onClick={() => logout()}
          disabled={isLoggingOut}
          className="w-full justify-start gap-3 px-3 text-muted-foreground hover:text-[hsl(var(--destructive-muted))]"
        >
          <LogOut className="h-4 w-4" />
          {isLoggingOut ? 'Logging out...' : 'Logout'}
        </Button>
      </div>
    </aside>
  );
}
