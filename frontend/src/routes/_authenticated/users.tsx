import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Search } from 'lucide-react'

export const Route = createFileRoute('/_authenticated/users')({
  component: UsersPage,
})

// Mock data
const mockUsers = [
  {
    id: 'usr_abc123',
    email: 'john.doe@example.com',
    name: 'John Doe',
    connections: ['fitbit', 'strava'],
    status: 'active' as const,
    lastSync: '2 hours ago',
    dataPoints: '12.4K',
  },
  {
    id: 'usr_def456',
    email: 'jane.smith@example.com',
    name: 'Jane Smith',
    connections: ['garmin'],
    status: 'active' as const,
    lastSync: '5 minutes ago',
    dataPoints: '8.2K',
  },
  {
    id: 'usr_ghi789',
    email: 'bob.wilson@example.com',
    name: 'Bob Wilson',
    connections: ['whoop', 'oura'],
    status: 'error' as const,
    lastSync: '2 days ago',
    dataPoints: '15.7K',
  },
  {
    id: 'usr_jkl012',
    email: 'alice.johnson@example.com',
    name: 'Alice Johnson',
    connections: ['fitbit', 'strava', 'garmin'],
    status: 'active' as const,
    lastSync: '1 hour ago',
    dataPoints: '23.1K',
  },
  {
    id: 'usr_mno345',
    email: 'charlie.brown@example.com',
    name: 'Charlie Brown',
    connections: [],
    status: 'pending' as const,
    lastSync: 'Never',
    dataPoints: '0',
  },
]

function UsersPage() {
  const [search, setSearch] = useState('')

  const filteredUsers = mockUsers.filter(
    (user) =>
      user.name.toLowerCase().includes(search.toLowerCase()) ||
      user.email.toLowerCase().includes(search.toLowerCase())
  )

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-500'
      case 'error':
        return 'bg-red-500'
      case 'pending':
        return 'bg-yellow-500'
      default:
        return 'bg-gray-500'
    }
  }

  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <div className="flex items-center justify-between space-y-2">
        <h2 className="text-3xl font-bold tracking-tight">Users</h2>
        <Button>Add User</Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Users</CardTitle>
          <CardDescription>
            Manage your platform users and their connections
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Search */}
          <div className="relative mb-4">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search users..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8"
            />
          </div>

          {/* Table */}
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Connections</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Sync</TableHead>
                  <TableHead>Data Points</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredUsers.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center">
                      No users found
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredUsers.map((user) => (
                    <TableRow key={user.id}>
                      <TableCell className="font-medium">{user.name}</TableCell>
                      <TableCell>{user.email}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {user.connections.map((conn) => (
                            <Badge key={conn} variant="secondary">
                              {conn}
                            </Badge>
                          ))}
                          {user.connections.length === 0 && (
                            <span className="text-sm text-muted-foreground">None</span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <span className={`h-2 w-2 rounded-full ${getStatusColor(user.status)}`} />
                          <span className="capitalize">{user.status}</span>
                        </div>
                      </TableCell>
                      <TableCell>{user.lastSync}</TableCell>
                      <TableCell>{user.dataPoints}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm">
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
