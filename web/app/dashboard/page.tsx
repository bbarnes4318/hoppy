"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { KpiCard } from "@/components/KpiCard";
import { TimeSeriesChart } from "@/components/TimeSeriesChart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useState, useEffect } from "react";
import { format, subDays } from "date-fns";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useWebSocket } from "@/hooks/useWebSocket";

type DateRange = "today" | "7d" | "30d" | "custom";

export default function DashboardPage() {
  const [dateRange, setDateRange] = useState<DateRange>("30d");
  const [partnerId, setPartnerId] = useState<string | undefined>(undefined);
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
  }, [dateRange]);

  // Fetch metrics summary
  const { data: metrics, refetch: refetchMetrics } = useQuery({
    queryKey: ["metrics-summary", fromDate.toISOString(), toDate.toISOString(), partnerId],
    queryFn: () =>
      api.getMetricsSummary({
        from: fromDate.toISOString(),
        to: toDate.toISOString(),
        partner_id: partnerId,
      }),
  });

  // Fetch time series
  const { data: timeSeries } = useQuery({
    queryKey: ["metrics-timeseries", fromDate.toISOString(), toDate.toISOString(), partnerId],
    queryFn: () =>
      api.getTimeSeries({
        interval: dateRange === "today" ? "hour" : "day",
        from: fromDate.toISOString(),
        to: toDate.toISOString(),
        partner_id: partnerId,
      }),
  });

  // Fetch partners
  const { data: partners } = useQuery({
    queryKey: ["partners"],
    queryFn: () => api.getPartners(),
  });

  // WebSocket for real-time updates
  useWebSocket({
    onMessage: (message) => {
      if (message.type === "call_ingested") {
        refetchMetrics();
      }
    },
  });

  const formatCurrency = (cents: number | null | undefined) => {
    if (!cents) return "$0.00";
    return `$${(cents / 100).toFixed(2)}`;
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            Real-time lead results overview
          </p>
        </div>
        <div className="flex gap-4">
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
          {partners && partners.length > 0 && (
            <Select
              value={partnerId || "all"}
              onValueChange={(v) => setPartnerId(v === "all" ? undefined : v)}
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
      </div>

      {/* Date Range Display */}
      <div className="text-sm text-muted-foreground">
        {format(fromDate, "MMM dd, yyyy")} - {format(toDate, "MMM dd, yyyy")}
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          title="Total Calls"
          value={metrics?.total_calls || 0}
          tooltip="Total number of calls in the selected period"
        />
        <KpiCard
          title="Billable Calls"
          value={metrics?.billable_calls || 0}
          tooltip="Calls that meet billability criteria"
        />
        <KpiCard
          title="Sales"
          value={metrics?.sales || 0}
          tooltip="Number of calls that resulted in sales"
        />
        <KpiCard
          title="Closing %"
          value={`${metrics?.closing_percentage.toFixed(1) || 0}%`}
          tooltip="Percentage of billable calls that resulted in sales"
        />
        <KpiCard
          title="Answer Rate"
          value={`${metrics?.answer_rate.toFixed(1) || 0}%`}
          tooltip="Percentage of calls that were answered"
        />
        <KpiCard
          title="AOV"
          value={formatCurrency(metrics?.aov_cents)}
          tooltip="Average Order Value"
        />
      </div>

      {/* Charts */}
      <div className="grid gap-4 md:grid-cols-2">
        {timeSeries && (
          <>
            <TimeSeriesChart
              title="Total Calls Over Time"
              data={timeSeries.points}
              dataKey="total_calls"
              color="#3b82f6"
            />
            <TimeSeriesChart
              title="Billable Calls Over Time"
              data={timeSeries.points}
              dataKey="billable_calls"
              color="#10b981"
            />
            <TimeSeriesChart
              title="Sales Over Time"
              data={timeSeries.points}
              dataKey="sales"
              color="#f59e0b"
            />
            <TimeSeriesChart
              title="Connected Calls Over Time"
              data={timeSeries.points}
              dataKey="connected"
              color="#8b5cf6"
            />
          </>
        )}
      </div>
    </div>
  );
}

