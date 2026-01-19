import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useState, useRef, useMemo, type ReactNode } from 'react';
import {
  ArrowLeft,
  Link as LinkIcon,
  Trash2,
  Check,
  Upload,
  Loader2,
  Key,
  Copy,
  User,
  Dumbbell,
  Activity,
  Moon,
  Scale,
  type LucideIcon,
} from 'lucide-react';
import {
  useUser,
  useDeleteUser,
  useAppleXmlUpload,
  useGenerateUserToken,
} from '@/hooks/api/use-users';
import { copyToClipboard } from '@/lib/utils/clipboard';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ProfileSection } from '@/components/user/profile-section';
import { SleepSection } from '@/components/user/sleep-section';
import { ActivitySection } from '@/components/user/activity-section';
import { BodySection } from '@/components/user/body-section';
import { WorkoutSection } from '@/components/user/workout-section';
import type { DateRangeValue } from '@/components/ui/date-range-selector';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

export const Route = createFileRoute('/_authenticated/users/$userId')({
  component: UserDetailPage,
});

interface TabConfig {
  id: string;
  label: string;
  icon: LucideIcon;
  content: ReactNode;
}

function UserDetailPage() {
  const { userId } = Route.useParams();
  const navigate = useNavigate();
  const { data: user, isLoading: userLoading } = useUser(userId);

  // Tab state
  const [activeTab, setActiveTab] = useState('profile');

  // Date range states for different sections
  const [workoutDateRange, setWorkoutDateRange] = useState<DateRangeValue>(30);
  const [activityDateRange, setActivityDateRange] =
    useState<DateRangeValue>(30);
  const [sleepDateRange, setSleepDateRange] = useState<DateRangeValue>(30);

  const { mutate: deleteUser, isPending: isDeleting } = useDeleteUser();
  const { handleUpload, isUploading: isUploadingFile } = useAppleXmlUpload();
  const {
    mutate: generateToken,
    data: tokenData,
    isPending: isGeneratingToken,
  } = useGenerateUserToken();
  const [copied, setCopied] = useState(false);
  const [tokenCopied, setTokenCopied] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isTokenDialogOpen, setIsTokenDialogOpen] = useState(false);
  const [editForm, setEditForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    external_user_id: '',
  });
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isUploading = isUploadingFile(userId);

  // Tab configuration
  const tabs: TabConfig[] = useMemo(
    () => [
      {
        id: 'profile',
        label: 'Profile',
        icon: User,
        content: <ProfileSection userId={userId} />,
      },
      {
        id: 'workouts',
        label: 'Workouts',
        icon: Dumbbell,
        content: (
          <WorkoutSection
            userId={userId}
            dateRange={workoutDateRange}
            onDateRangeChange={setWorkoutDateRange}
          />
        ),
      },
      {
        id: 'activity',
        label: 'Activity',
        icon: Activity,
        content: (
          <ActivitySection
            userId={userId}
            dateRange={activityDateRange}
            onDateRangeChange={setActivityDateRange}
          />
        ),
      },
      {
        id: 'sleep',
        label: 'Sleep',
        icon: Moon,
        content: (
          <SleepSection
            userId={userId}
            dateRange={sleepDateRange}
            onDateRangeChange={setSleepDateRange}
          />
        ),
      },
      {
        id: 'body',
        label: 'Body',
        icon: Scale,
        content: <BodySection userId={userId} />,
      },
    ],
    [userId, workoutDateRange, activityDateRange, sleepDateRange]
  );

  const handleCopyPairLink = async () => {
    const pairLink = `${window.location.origin}/users/${userId}/pair`;
    const success = await copyToClipboard(
      pairLink,
      'Pairing link copied to clipboard'
    );
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleDelete = () => {
    deleteUser(userId, {
      onSuccess: () => {
        navigate({ to: '/users' });
      },
    });
  };

  const handleEditSubmit = () => {
    updateUser(
      {
        id: userId,
        data: {
          first_name: editForm.first_name || null,
          last_name: editForm.last_name || null,
          email: editForm.email || null,
          external_user_id: editForm.external_user_id || null,
        },
      },
      {
        onSuccess: () => {
          setIsEditDialogOpen(false);
        },
      }
    );
  };

  const handleGenerateToken = () => {
    generateToken(userId, {
      onSuccess: () => {
        setIsTokenDialogOpen(true);
      },
    });
  };

  const handleCopyToken = async () => {
    if (tokenData?.access_token) {
      await navigator.clipboard.writeText(tokenData.access_token);
      setTokenCopied(true);
      toast.success('Token copied to clipboard');
      setTimeout(() => setTokenCopied(false), 2000);
    }
  };

  if (!userLoading && !user) {
    return (
      <div className="p-8">
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
          <p className="text-zinc-400">User not found</p>
          <Link
            to="/users"
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-zinc-800 text-white rounded-md text-sm font-medium hover:bg-zinc-700 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Users
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/users"
            className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-md transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          {userLoading ? (
            <div className="space-y-2">
              <div className="h-7 w-48 bg-zinc-800 rounded animate-pulse" />
              <div className="h-4 w-32 bg-zinc-800/50 rounded animate-pulse" />
            </div>
          ) : (
            <div>
              <h1 className="text-2xl font-medium text-white">
                {user?.first_name || user?.last_name
                  ? `${user?.first_name || ''} ${user?.last_name || ''}`.trim()
                  : 'Unnamed User'}
              </h1>
              <p className="text-sm text-zinc-500">
                {user?.email || 'No email'}
              </p>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleUploadClick}
            disabled={isUploading}
            className="flex items-center gap-2 px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isUploading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4" />
                Upload Apple Health XML
              </>
            )}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xml"
            onChange={(e) => handleUpload(userId, e)}
            className="hidden"
          />
          <button
            onClick={handleCopyPairLink}
            className="flex items-center gap-2 px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors"
          >
            {copied ? (
              <>
                <Check className="h-4 w-4 text-emerald-600" />
                Copied!
              </>
            ) : (
              <>
                <LinkIcon className="h-4 w-4" />
                Copy Pairing Link
              </>
            )}
          </button>
          <button
            onClick={handleGenerateToken}
            disabled={isGeneratingToken}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isGeneratingToken ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Key className="h-4 w-4" />
                Generate Token
              </>
            )}
          </button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <button
                disabled={isDeleting}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-md text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Trash2 className="h-4 w-4" />
                {isDeleting ? 'Deleting...' : 'Delete User'}
              </button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete User</AlertDialogTitle>
                <AlertDialogDescription>
                  Are you sure you want to delete this user? This action cannot
                  be undone and will permanently remove all associated data.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleDelete}
                  className="bg-red-600 text-white hover:bg-red-700"
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          {tabs.map((tab) => (
            <TabsTrigger key={tab.id} value={tab.id} className="gap-2">
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {tabs.map((tab) => (
          <TabsContent key={tab.id} value={tab.id} className="space-y-6">
            {tab.content}
          </TabsContent>
        ))}
      </Tabs>

      {/* Data Points Section */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h3 className="text-sm font-medium text-white">Data Points</h3>
            <DateRangeSelector
              value={dataPointsDateRange}
              onChange={setDataPointsDateRange}
            />
          </div>
          <Activity className="h-4 w-4 text-zinc-500" />
        </div>
        <div className="p-6">
          {timeSeriesLoading ? (
            <div className="space-y-3">
              <div className="h-8 w-20 bg-zinc-800 rounded animate-pulse" />
              <div className="h-4 w-28 bg-zinc-800/50 rounded animate-pulse" />
            </div>
          ) : timeSeries?.data && timeSeries.data.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Energy Card */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-orange-500/10 rounded-lg">
                    <Flame className="h-5 w-5 text-orange-500" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-300">Energy</p>
                    <p className="text-xs text-zinc-500">Total Calories</p>
                  </div>
                </div>
                <div className="mt-2">
                  <p className="text-2xl font-semibold text-white">
                    {processedTimeSeries.energy
                      .reduce((acc, curr) => acc + curr.value, 0)
                      .toLocaleString()}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">kcal</p>
                </div>
              </div>

              {/* Steps Card */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-emerald-500/10 rounded-lg">
                    <Footprints className="h-5 w-5 text-emerald-500" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-300">Steps</p>
                    <p className="text-xs text-zinc-500">Total Steps</p>
                  </div>
                </div>
                <div className="mt-2">
                  <p className="text-2xl font-semibold text-white">
                    {processedTimeSeries.steps
                      .reduce((acc, curr) => acc + curr.value, 0)
                      .toLocaleString()}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">steps</p>
                </div>
              </div>

              {/* Heart Rate Card */}
              <div className="p-4 border border-zinc-800 rounded-lg bg-zinc-900/30">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-rose-500/10 rounded-lg">
                    <Heart className="h-5 w-5 text-rose-500" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-300">
                      Heart Rate
                    </p>
                    <p className="text-xs text-zinc-500">Average BPM</p>
                  </div>
                </div>
                <div className="mt-2">
                  <p className="text-2xl font-semibold text-white">
                    {processedTimeSeries.heartRate.length > 0
                      ? Math.round(
                          processedTimeSeries.heartRate.reduce(
                            (acc, curr) => acc + curr.value,
                            0
                          ) / processedTimeSeries.heartRate.length
                        )
                      : '-'}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">bpm</p>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-zinc-500 text-center">
              No data points available yet
            </p>
          )}
        </div>
      </div>

      {/* Edit User Dialog */}
      {isEditDialogOpen && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md shadow-2xl">
            <div className="p-6 border-b border-zinc-800 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-medium text-white">Edit User</h2>
                <p className="text-sm text-zinc-500 mt-1">
                  Update user information
                </p>
              </div>
              <button
                onClick={() => setIsEditDialogOpen(false)}
                className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-md transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="first_name" className="text-zinc-300">
                    First Name
                  </Label>
                  <Input
                    id="first_name"
                    value={editForm.first_name}
                    onChange={(e) =>
                      setEditForm({ ...editForm, first_name: e.target.value })
                    }
                    placeholder="John"
                    className="bg-zinc-800 border-zinc-700"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="last_name" className="text-zinc-300">
                    Last Name
                  </Label>
                  <Input
                    id="last_name"
                    value={editForm.last_name}
                    onChange={(e) =>
                      setEditForm({ ...editForm, last_name: e.target.value })
                    }
                    placeholder="Doe"
                    className="bg-zinc-800 border-zinc-700"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="email" className="text-zinc-300">
                  Email
                </Label>
                <Input
                  id="email"
                  type="email"
                  value={editForm.email}
                  onChange={(e) =>
                    setEditForm({ ...editForm, email: e.target.value })
                  }
                  placeholder="john@example.com"
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="external_user_id" className="text-zinc-300">
                  External User ID
                </Label>
                <Input
                  id="external_user_id"
                  value={editForm.external_user_id}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      external_user_id: e.target.value,
                    })
                  }
                  placeholder="external-123"
                  className="bg-zinc-800 border-zinc-700"
                />
                <p className="text-xs text-zinc-500">
                  Optional identifier from your system
                </p>
              </div>
            </div>
            <div className="p-6 border-t border-zinc-800 flex justify-end gap-3">
              <button
                onClick={() => setIsEditDialogOpen(false)}
                className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-md transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleEditSubmit}
                disabled={isUpdating}
                className="px-4 py-2 text-sm font-medium bg-white text-black rounded-md hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isUpdating ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Token Dialog */}
      <Dialog open={isTokenDialogOpen} onOpenChange={setIsTokenDialogOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>User Token Generated</DialogTitle>
            <DialogDescription>
              This token is valid for 60 minutes and can be used to access SDK
              endpoints for this user. Store it securely.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="token" className="text-zinc-300">
                Access Token
              </Label>
              <div className="flex items-center gap-2">
                <Input
                  id="token"
                  readOnly
                  value={tokenData?.access_token || ''}
                  className="bg-zinc-800 border-zinc-700 font-mono text-sm"
                />
                <Button
                  onClick={handleCopyToken}
                  variant="outline"
                  size="icon"
                  className="shrink-0"
                >
                  {tokenCopied ? (
                    <Check className="h-4 w-4 text-emerald-500" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <p className="text-xs text-zinc-500">
                Token type: {tokenData?.token_type || 'bearer'}
              </p>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
