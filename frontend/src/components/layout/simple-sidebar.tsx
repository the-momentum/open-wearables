import { Link, useLocation } from '@tanstack/react-router'
import {
  Home,
  Users,
  Activity,
  Key,
  FileText,
  LogOut,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'

const menuItems = [
  {
    title: 'Dashboard',
    url: '/_authenticated/dashboard',
    icon: Home,
  },
  {
    title: 'Users',
    url: '/_authenticated/users',
    icon: Users,
  },
  {
    title: 'Health Insights',
    url: '/_authenticated/health-insights',
    icon: Activity,
  },
  {
    title: 'Credentials',
    url: '/_authenticated/credentials',
    icon: Key,
  },
  {
    title: 'Documentation',
    url: '/_authenticated/docs',
    icon: FileText,
  },
]

export function SimpleSidebar() {
  const location = useLocation()

  const handleLogout = () => {
    window.location.href = '/login'
  }

  return (
    <aside className="w-64 border-r border-border bg-card flex flex-col">
      <div className="border-b border-border p-4">
        <div className="flex items-center gap-2">
          <Activity className="h-6 w-6 text-primary" />
          <div>
            <h2 className="text-lg font-semibold">Open Wearables</h2>
            <p className="text-xs text-muted-foreground">Platform Dashboard</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {menuItems.map((item) => {
          const isActive = location.pathname === item.url
          return (
            <Link
              key={item.title}
              to={item.url}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )}
            >
              <item.icon className="h-4 w-4" />
              <span>{item.title}</span>
            </Link>
          )
        })}
      </nav>

      <Separator />

      <div className="p-4">
        <Button
          variant="ghost"
          className="w-full justify-start"
          onClick={handleLogout}
        >
          <LogOut className="mr-2 h-4 w-4" />
          Logout
        </Button>
      </div>
    </aside>
  )
}
