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
import { ClipboardList } from 'lucide-react';
import type { RecordListResponse } from '@/lib/api/types';
import { format } from 'date-fns';

interface RecordsTableProps {
  data: RecordListResponse;
  isLoading?: boolean;
}

export function RecordsTable({ data, isLoading }: RecordsTableProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ClipboardList className="h-5 w-5 text-purple-500" />
            Health Records
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-48 flex items-center justify-center text-muted-foreground">
            Loading records...
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ClipboardList className="h-5 w-5 text-purple-500" />
          Health Records
        </CardTitle>
        <CardDescription>
          {data.meta.total_count} total records
        </CardDescription>
      </CardHeader>
      <CardContent>
        {data.data.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-muted-foreground">
            No health records available
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Value</TableHead>
                  <TableHead>Unit</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Source</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.data.map((record) => (
                  <TableRow key={record.id}>
                    <TableCell>
                      <Badge variant="outline">{record.type}</Badge>
                    </TableCell>
                    <TableCell className="font-medium">{record.value}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {record.unit}
                    </TableCell>
                    <TableCell>
                      {format(new Date(record.startDate), 'MMM dd, yyyy HH:mm')}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {record.sourceName}
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
