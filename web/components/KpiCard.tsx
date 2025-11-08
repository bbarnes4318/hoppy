"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  title: string;
  value: string | number;
  delta?: number;
  deltaLabel?: string;
  tooltip?: string;
  className?: string;
}

export function KpiCard({
  title,
  value,
  delta,
  deltaLabel,
  tooltip,
  className,
}: KpiCardProps) {
  const isPositive = delta !== undefined && delta >= 0;
  const deltaDisplay = delta !== undefined ? Math.abs(delta).toFixed(1) : null;

  return (
    <Card className={cn("", className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {tooltip && (
          <span className="text-xs text-muted-foreground" title={tooltip}>
            ℹ️
          </span>
        )}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {delta !== undefined && deltaLabel && (
          <div
            className={cn(
              "flex items-center text-xs mt-1",
              isPositive ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
            )}
          >
            {isPositive ? (
              <TrendingUp className="mr-1 h-3 w-3" />
            ) : (
              <TrendingDown className="mr-1 h-3 w-3" />
            )}
            <span>
              {deltaDisplay}% {deltaLabel}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

