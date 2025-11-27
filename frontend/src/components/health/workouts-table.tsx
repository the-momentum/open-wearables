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
import { Badge } from '@/components/ui/badge';
import { Activity } from 'lucide-react';
import type { WorkoutListResponse } from '@/lib/api/types';
import { format } from 'date-fns';

interface WorkoutsTableProps {
  data: WorkoutListResponse;
  isLoading?: boolean;
}

function formatDuration(duration: number, unit: string): string {
  if (unit === 'min' || unit === 'minutes') {
    const hours = Math.floor(duration / 60);
    const minutes = Math.round(duration % 60);
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  }
  if (unit === 's' || unit === 'seconds') {
    const minutes = Math.floor(duration / 60);
    const seconds = Math.round(duration % 60);
    if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    }
    return `${seconds}s`;
  }
  return `${duration} ${unit}`;
}

export function WorkoutsTable({ data, isLoading }: WorkoutsTableProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-blue-500" />
            Workouts
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-48 flex items-center justify-center text-muted-foreground">
            Loading workouts...
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-blue-500" />
          Workouts
        </CardTitle>
        <CardDescription>
          {data.meta.total_count} total workouts
        </CardDescription>
      </CardHeader>
      <CardContent>
        {data.data.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-muted-foreground">
            No workouts available
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Avg HR</TableHead>
                  <TableHead>Max HR</TableHead>
                  <TableHead>Calories</TableHead>
                  <TableHead>Source</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.data.map((workout) => (
                  <TableRow key={workout.id}>
                    <TableCell>
                      <Badge variant="outline">
                        {workout.type || 'Unknown'}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {format(
                        new Date(workout.startDate),
                        'MMM dd, yyyy HH:mm'
                      )}
                    </TableCell>
                    <TableCell>
                      {formatDuration(workout.duration, workout.durationUnit)}
                    </TableCell>
                    <TableCell>
                      {workout.summary.avg_heart_rate > 0
                        ? `${workout.summary.avg_heart_rate.toFixed(0)} bpm`
                        : '-'}
                    </TableCell>
                    <TableCell>
                      {workout.summary.max_heart_rate > 0
                        ? `${workout.summary.max_heart_rate.toFixed(0)} bpm`
                        : '-'}
                    </TableCell>
                    <TableCell>
                      {workout.summary.total_calories > 0
                        ? `${workout.summary.total_calories.toFixed(0)} kcal`
                        : '-'}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {workout.sourceName || '-'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
