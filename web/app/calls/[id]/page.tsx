"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { format } from "date-fns";
import { Loader2 } from "lucide-react";

export default function CallDetailPage() {
  const params = useParams();
  const callId = params.id as string;

  // Fetch call details
  const { data: call, isLoading: callLoading } = useQuery({
    queryKey: ["call", callId],
    queryFn: () => api.getCall(callId),
  });

  // Fetch transcript
  const { data: transcript, isLoading: transcriptLoading } = useQuery({
    queryKey: ["call-transcript", callId],
    queryFn: () => api.getCallTranscript(callId),
    enabled: !!callId,
  });

  // Fetch summary
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["call-summary", callId],
    queryFn: () => api.getCallSummary(callId),
    enabled: !!callId,
  });

  if (callLoading) {
    return (
      <div className="container mx-auto p-6 flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!call) {
    return (
      <div className="container mx-auto p-6">
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-muted-foreground">Call not found</p>
          </CardContent>
        </Card>
      </div>
    );
  }

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

  const getSentimentBadge = (sentiment: string | null) => {
    if (!sentiment) return null;
    const variants: Record<string, "success" | "warning" | "destructive"> = {
      pos: "success",
      neu: "warning",
      neg: "destructive",
    };
    return (
      <Badge variant={variants[sentiment] || "default"}>
        {sentiment === "pos" ? "Positive" : sentiment === "neu" ? "Neutral" : "Negative"}
      </Badge>
    );
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Call Details</h1>
        <p className="text-muted-foreground mt-1">
          {call.external_call_id || call.id}
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Disposition</CardTitle>
          </CardHeader>
          <CardContent>
            {getDispositionBadge(call.disposition)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Billable</CardTitle>
          </CardHeader>
          <CardContent>
            {call.billable ? (
              <Badge variant="success">Yes</Badge>
            ) : (
              <Badge variant="secondary">No</Badge>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Sale Made</CardTitle>
          </CardHeader>
          <CardContent>
            {call.sale_made ? (
              <Badge variant="success">
                {call.sale_amount_cents
                  ? `$${(call.sale_amount_cents / 100).toFixed(2)}`
                  : "Yes"}
              </Badge>
            ) : (
              <Badge variant="secondary">No</Badge>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Duration</CardTitle>
          </CardHeader>
          <CardContent>
            {call.duration_sec
              ? `${Math.floor(call.duration_sec / 60)}:${String(
                  call.duration_sec % 60
                ).padStart(2, "0")}`
              : "-"}
          </CardContent>
        </Card>
      </div>

      {/* Metadata */}
      <Card>
        <CardHeader>
          <CardTitle>Call Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Started At</p>
              <p className="font-medium">
                {format(new Date(call.started_at), "MMM dd, yyyy HH:mm:ss")}
              </p>
            </div>
            {call.ended_at && (
              <div>
                <p className="text-sm text-muted-foreground">Ended At</p>
                <p className="font-medium">
                  {format(new Date(call.ended_at), "MMM dd, yyyy HH:mm:ss")}
                </p>
              </div>
            )}
            {call.ani && (
              <div>
                <p className="text-sm text-muted-foreground">Caller (ANI)</p>
                <p className="font-medium">{call.ani}</p>
              </div>
            )}
            {call.dnis && (
              <div>
                <p className="text-sm text-muted-foreground">Destination (DNIS)</p>
                <p className="font-medium">{call.dnis}</p>
              </div>
            )}
            {call.agent_name && (
              <div>
                <p className="text-sm text-muted-foreground">Agent</p>
                <p className="font-medium">{call.agent_name}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Summary */}
      {summary && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Summary</CardTitle>
              {getSentimentBadge(summary.sentiment)}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {summaryLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <p className="text-sm whitespace-pre-wrap">{summary.summary}</p>
                {summary.key_points && summary.key_points.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2">Key Points:</p>
                    <ul className="list-disc list-inside space-y-1">
                      {summary.key_points.map((point, idx) => (
                        <li key={idx} className="text-sm">
                          {point}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* Transcript */}
      {transcript && (
        <Card>
          <CardHeader>
            <CardTitle>Transcript</CardTitle>
          </CardHeader>
          <CardContent>
            {transcriptLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <div className="prose prose-sm max-w-none">
                <p className="whitespace-pre-wrap text-sm">{transcript.text}</p>
                {transcript.language && (
                  <p className="text-xs text-muted-foreground mt-2">
                    Language: {transcript.language}
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

