import { Link, useLocation } from '@tanstack/react-router';
import {
  Home,
  Users,
  FileText,
  LogOut,
  Settings,
  ExternalLink,
} from 'lucide-react';
import logotype from '@/logotype.svg';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/use-auth';
import { Button } from '@/components/ui/button';

const menuItems = [
  {
    title: 'Dashboard',
    url: '/dashboard',
    icon: Home,
  },
  {
    title: 'Users',
    url: '/users',
    icon: Users,
  },
  {
    title: 'Settings',
    url: '/settings',
    icon: Settings,
  },
  {
    title: 'Documentation',
    url: 'https://docs.openwearables.io/',
    icon: FileText,
    external: true,
  },
];

export function SimpleSidebar() {
  const location = useLocation();
  const { logout, isLoggingOut } = useAuth();

  return (
    <aside className="relative w-64 bg-black flex flex-col border-r border-zinc-900">
      {/* Header */}
      <div className="p-4 border-b border-zinc-900">
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
                className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-zinc-400 hover:bg-zinc-900/50 hover:text-zinc-200 transition-all duration-200"
              >
                <item.icon className="h-4 w-4 text-zinc-500" />
                <span>{item.title}</span>
                <ExternalLink className="ml-auto h-3 w-3 text-zinc-600" />
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
                  ? 'bg-zinc-900 text-white border-l-2 border-white -ml-[2px] pl-[calc(0.75rem+2px)]'
                  : 'text-zinc-400 hover:bg-zinc-900/50 hover:text-zinc-200'
              )}
            >
              <item.icon
                className={cn(
                  'h-4 w-4 transition-colors',
                  isActive ? 'text-white' : 'text-zinc-500'
                )}
              />
              <span>{item.title}</span>
            </Link>
          );
        })}
      </nav>

      {/* Divider */}
      <div className="mx-3 border-t border-zinc-900" />

      {/* Footer */}
      <div className="p-3">
        <Button
          variant="ghost"
          onClick={() => logout()}
          disabled={isLoggingOut}
          className="w-full justify-start gap-3 px-3 text-zinc-400 hover:text-red-400"
        >
          <LogOut className="h-4 w-4" />
          {isLoggingOut ? 'Logging out...' : 'Logout'}
        </Button>
      </div>
    </aside>
  );
}
