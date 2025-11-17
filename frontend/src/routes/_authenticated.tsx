import { createFileRoute, Outlet } from '@tanstack/react-router'
import { SimpleSidebar } from '@/components/layout/simple-sidebar'

export const Route = createFileRoute('/_authenticated')({
  component: AuthenticatedLayout,
})

function AuthenticatedLayout() {
  return (
    <div className="flex min-h-screen w-full">
      <SimpleSidebar />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
