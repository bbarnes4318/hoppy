"use client";

import { useQuery } from "@tanstack/react-query";
import { api, CallResponse } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useState, useEffect } from "react";
import { format, subDays } from "date-fns";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useRouter } from "next/navigation";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

type DateRange = "today" | "7d" | "30d";

export default function CallsPage() {
  const router = useRouter();
  const [dateRange, setDateRange] = useState<DateRange>("30d");
  const [partnerId, setPartnerId] = useState<string | undefined>(undefined);
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [fromDate, setFromDate] = useState<Date>(subDays(new Date(), 30));
  const [toDate, setToDate] = useState<Date>(new Date());

  // Update date range
  useEffect(() => {
    const now = new Date();
    switch (dateRange) {
      case "today":
        setFromDate(new Date(now.setHours(0, 0, 0, 0)));
        setToDate(new Date());
        break;
      case "7d":
        setFromDate(subDays(now, 7));
        setToDate(now);
        break;
      case "30d":
        setFromDate(subDays(now, 30));
        setToDate(now);
        break;
    }
    setPage(1); // Reset to first page when filters change
  }, [dateRange]);

  // Fetch calls
  const { data: callsData, isLoading } = useQuery({
    queryKey: [
      "calls",
      fromDate.toISOString(),
      toDate.toISOString(),
      partnerId,
      searchQuery,
      page,
    ],
    queryFn: () =>
      api.getCalls({
        from: fromDate.toISOString(),
        to: toDate.toISOString(),
        partner_id: partnerId,
        q: searchQuery || undefined,
        page,
        page_size: 50,
      }),
  });

  // Fetch partners
  const { data: partners } = useQuery({
    queryKey: ["partners"],
    queryFn: () => api.getPartners(),
  });

  const getDispositionBadge = (disposition: string) => {
    const variants: Record<string, "default" | "success" | "warning" | "destructive"> = {
      connected: "success",
      no_answer: "warning",
      busy: "warning",
      failed: "destructive",
      rejected: "destructive",
    };
    return (
      <Badge variant={variants[disposition] || "default"}>
        {disposition.replace("_", " ")}
      </Badge>
    );
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Calls</h1>
          <p className="text-muted-foreground mt-1">
            View and search call records
          </p>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4">
            {/* Search */}
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search calls, transcripts, phone numbers..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setPage(1);
                }}
                className="w-full pl-10 pr-4 py-2 border rounded-md bg-background"
              />
            </div>

            {/* Date Range */}
            <Select value={dateRange} onValueChange={(v) => setDateRange(v as DateRange)}>
              <SelectTrigger className="w-[180px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="today">Today</SelectItem>
                <SelectItem value="7d">Last 7 Days</SelectItem>
                <SelectItem value="30d">Last 30 Days</SelectItem>
              </SelectContent>
            </Select>

            {/* Partner Filter */}
            {partners && partners.length > 0 && (
              <Select
                value={partnerId || "all"}
                onValueChange={(v) => {
                  setPartnerId(v === "all" ? undefined : v);
                  setPage(1);
                }}
              >
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="All Partners" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Partners</SelectItem>
                  {partners.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Calls Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-8 text-center text-muted-foreground">
              Loading calls...
            </div>
          ) : callsData && callsData.items.length > 0 ? (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="border-b">
                    <tr>
                      <th className="text-left p-4 font-medium">Call ID</th>
                      <th className="text-left p-4 font-medium">Started</th>
                      <th className="text-left p-4 font-medium">Duration</th>
                      <th className="text-left p-4 font-medium">Disposition</th>
                      <th className="text-left p-4 font-medium">Billable</th>
                      <th className="text-left p-4 font-medium">Sale</th>
                      <th className="text-left p-4 font-medium">Agent</th>
                      <th className="text-left p-4 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {callsData.items.map((call: CallResponse) => (
                      <tr
                        key={call.id}
                        className="border-b hover:bg-muted/50 transition-colors"
                      >
                        <td className="p-4">
                          <div className="font-mono text-sm">
                            {call.external_call_id || call.id.slice(0, 8)}
                          </div>
                        </td>
                        <td className="p-4 text-sm">
                          {format(new Date(call.started_at), "MMM dd, yyyy HH:mm")}
                        </td>
                        <td className="p-4 text-sm">
                          {call.duration_sec
                            ? `${Math.floor(call.duration_sec / 60)}:${String(
                                call.duration_sec % 60
                              ).padStart(2, "0")}`
                            : "-"}
                        </td>
                        <td className="p-4">{getDispositionBadge(call.disposition)}</td>
                        <td className="p-4">
                          {call.billable ? (
                            <Badge variant="success">Yes</Badge>
                          ) : (
                            <Badge variant="secondary">No</Badge>
                          )}
                        </td>
                        <td className="p-4">
                          {call.sale_made ? (
                            <Badge variant="success">
                              {call.sale_amount_cents
                                ? `$${(call.sale_amount_cents / 100).toFixed(2)}`
                                : "Yes"}
                            </Badge>
                          ) : (
                            <Badge variant="secondary">No</Badge>
                          )}
                        </td>
                        <td className="p-4 text-sm">{call.agent_name || "-"}</td>
                        <td className="p-4">
                          <Link href={`/calls/${call.id}`}>
                            <Button variant="outline" size="sm">
                              View
                            </Button>
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {callsData.total_pages > 1 && (
                <div className="flex items-center justify-between p-4 border-t">
                  <div className="text-sm text-muted-foreground">
                    Showing {((page - 1) * 50) + 1} to {Math.min(page * 50, callsData.total)} of{" "}
                    {callsData.total} calls
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.min(callsData.total_pages, p + 1))}
                      disabled={page === callsData.total_pages}
                    >
                      Next
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="p-8 text-center text-muted-foreground">
              No calls found. Try adjusting your filters.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

