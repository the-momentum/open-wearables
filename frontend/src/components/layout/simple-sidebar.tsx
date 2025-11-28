import { Link, useLocation } from '@tanstack/react-router';
import {
  Home,
  Users,
  Activity,
  Key,
  FileText,
  DollarSign,
  LogOut,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/use-auth';

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
    title: 'Health Insights',
    url: '/health-insights',
    icon: Activity,
  },
  {
    title: 'Credentials',
    url: '/credentials',
    icon: Key,
  },
  {
    title: 'Pricing',
    url: '/pricing',
    icon: DollarSign,
  },
  {
    title: 'Documentation',
    url: '/docs',
    icon: FileText,
    comingSoon: true,
  },
];

export function SimpleSidebar() {
  const location = useLocation();
  const { logout, isLoggingOut } = useAuth();

  return (
    <aside className="relative w-64 bg-black flex flex-col border-r border-zinc-900">
      {/* Header */}
      <div className="p-4 border-b border-zinc-900">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
            <Activity className="h-5 w-5 text-black" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white uppercase tracking-tight">
              Open Wearables
            </h2>
            <p className="text-[10px] text-zinc-500">Platform Dashboard</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        {menuItems.map((item) => {
          const isActive = location.pathname.startsWith(item.url);

          if (item.comingSoon) {
            return (
              <div
                key={item.title}
                className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-zinc-600 cursor-not-allowed"
              >
                <item.icon className="h-4 w-4" />
                <span>{item.title}</span>
                <span className="ml-auto text-[10px] text-zinc-700">(Soon)</span>
              </div>
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
        <button
          onClick={() => logout()}
          disabled={isLoggingOut}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm text-zinc-400 hover:bg-zinc-900/50 hover:text-red-400 transition-colors disabled:opacity-50"
        >
          <LogOut className="h-4 w-4" />
          {isLoggingOut ? 'Logging out...' : 'Logout'}
        </button>
      </div>
    </aside>
  );
}
