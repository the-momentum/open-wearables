import { createFileRoute } from '@tanstack/react-router';
import { useState } from 'react';
import { Plus, Eye, EyeOff, Copy, Trash2, Code } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import {
  useApiKeys,
  useCreateApiKey,
  useDeleteApiKey,
} from '@/hooks/api/use-credentials';
import { credentialsService } from '@/lib/api/services/credentials.service';
import { LoadingState } from '@/components/common/loading-spinner';
import { ErrorState } from '@/components/common/error-state';
import type { ApiKeyCreate } from '@/lib/api/types';
import { toast } from 'sonner';

export const Route = createFileRoute('/_authenticated/credentials')({
  component: CredentialsPage,
});

function CredentialsPage() {
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isEmbedDialogOpen, setIsEmbedDialogOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set());
  const [formData, setFormData] = useState<ApiKeyCreate>({
    name: '',
    type: 'live',
  });

  const { data: apiKeys, isLoading, error } = useApiKeys();
  const createMutation = useCreateApiKey();
  const deleteMutation = useDeleteApiKey();

  const handleCreate = async () => {
    if (!formData.name) {
      toast.error('Please enter a key name');
      return;
    }

    const newKey = await createMutation.mutateAsync(formData);
    setIsCreateDialogOpen(false);
    setFormData({ name: '', type: 'live' });

    // Show the new key
    toast.success('API key created successfully');
    setVisibleKeys((prev) => new Set(prev).add(newKey.id));
  };

  const handleDelete = async (id: string) => {
    if (
      confirm(
        'Are you sure you want to delete this API key? This action cannot be undone.'
      )
    ) {
      await deleteMutation.mutateAsync(id);
    }
  };

  const toggleKeyVisibility = (id: string) => {
    setVisibleKeys((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied to clipboard`);
  };

  const maskKey = (key: string) => {
    if (key.length < 10) return '****';
    return key.substring(0, 10) + '****' + key.substring(key.length - 4);
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  const getEmbedCode = (apiKey: string) => {
    return credentialsService.getWidgetEmbedCode(apiKey);
  };

  if (isLoading) {
    return <LoadingState message="Loading API keys..." />;
  }

  if (error) {
    return <ErrorState message="Failed to load API keys" />;
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">API Credentials</h1>
          <p className="text-muted-foreground mt-1">
            Manage your API keys and widget embed codes
          </p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create API Key
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>API Keys</CardTitle>
          <CardDescription>
            Use these keys to authenticate API requests and embed widgets
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Key</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Used</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {apiKeys && apiKeys.length > 0 ? (
                apiKeys.map((key) => (
                  <TableRow key={key.id}>
                    <TableCell className="font-medium">{key.name}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <code className="text-xs font-mono">
                          {visibleKeys.has(key.id) ? key.key : maskKey(key.key)}
                        </code>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => toggleKeyVisibility(key.id)}
                        >
                          {visibleKeys.has(key.id) ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(key.key, 'API key')}
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {key.type === 'live'
                          ? 'Live'
                          : key.type === 'test'
                            ? 'Test'
                            : 'Widget'}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          key.status === 'active' ? 'default' : 'secondary'
                        }
                      >
                        {key.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(key.lastUsed)}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        {key.type === 'widget' && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setSelectedKey(key.key);
                              setIsEmbedDialogOpen(true);
                            }}
                          >
                            <Code className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDelete(key.id)}
                          disabled={
                            deleteMutation.isPending || key.status === 'revoked'
                          }
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="text-center py-8 text-muted-foreground"
                  >
                    No API keys yet. Create your first key to get started.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New API Key</DialogTitle>
            <DialogDescription>
              Generate a new API key for your application
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="keyName">Key Name</Label>
              <Input
                id="keyName"
                placeholder="e.g., Production API Key"
                value={formData.name}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, name: e.target.value }))
                }
              />
              <p className="text-xs text-muted-foreground">
                A descriptive name to identify this key
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="keyType">Key Type</Label>
              <Select
                value={formData.type}
                onValueChange={(value) =>
                  setFormData((prev) => ({
                    ...prev,
                    type: value as 'live' | 'test' | 'widget',
                  }))
                }
              >
                <SelectTrigger id="keyType">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="live">
                    Live - Production API access
                  </SelectItem>
                  <SelectItem value="test">
                    Test - Development and testing
                  </SelectItem>
                  <SelectItem value="widget">
                    Widget - For embedded connect widget
                  </SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {formData.type === 'widget'
                  ? 'Use this key for the embeddable wearables connection widget'
                  : formData.type === 'test'
                    ? 'Test keys work with test mode only'
                    : 'Live keys have full access to production data'}
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsCreateDialogOpen(false)}
              disabled={createMutation.isPending}
            >
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Creating...' : 'Create Key'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Embed Code Dialog */}
      <Dialog open={isEmbedDialogOpen} onOpenChange={setIsEmbedDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Widget Embed Code</DialogTitle>
            <DialogDescription>
              Copy and paste these code snippets to embed the wearables
              connection widget
            </DialogDescription>
          </DialogHeader>

          {selectedKey && (
            <div className="space-y-6">
              {/* HTML Version */}
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <Label>HTML</Label>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      copyToClipboard(
                        getEmbedCode(selectedKey).html,
                        'HTML code'
                      )
                    }
                  >
                    <Copy className="mr-2 h-4 w-4" />
                    Copy
                  </Button>
                </div>
                <Textarea
                  readOnly
                  value={getEmbedCode(selectedKey).html}
                  rows={15}
                  className="font-mono text-xs"
                />
              </div>

              {/* React Version */}
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <Label>React / TypeScript</Label>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      copyToClipboard(
                        getEmbedCode(selectedKey).react,
                        'React code'
                      )
                    }
                  >
                    <Copy className="mr-2 h-4 w-4" />
                    Copy
                  </Button>
                </div>
                <Textarea
                  readOnly
                  value={getEmbedCode(selectedKey).react}
                  rows={20}
                  className="font-mono text-xs"
                />
              </div>
            </div>
          )}

          <DialogFooter>
            <Button onClick={() => setIsEmbedDialogOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
