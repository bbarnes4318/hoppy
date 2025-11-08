"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function PartnersPage() {
  const { data: partners, isLoading } = useQuery({
    queryKey: ["partners"],
    queryFn: () => api.getPartners(),
  });

  const getKindBadge = (kind: string) => {
    const variants: Record<string, "default" | "success" | "warning"> = {
      publisher: "default",
      agency: "success",
      broker: "warning",
    };
    return (
      <Badge variant={variants[kind] || "default"}>
        {kind.charAt(0).toUpperCase() + kind.slice(1)}
      </Badge>
    );
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Partners</h1>
        <p className="text-muted-foreground mt-1">
          Manage publishers, agencies, and brokers
        </p>
      </div>

      {isLoading ? (
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            Loading partners...
          </CardContent>
        </Card>
      ) : partners && partners.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {partners.map((partner) => (
            <Card key={partner.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{partner.name}</CardTitle>
                  {getKindBadge(partner.kind)}
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  ID: {partner.id.slice(0, 8)}...
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            No partners found
          </CardContent>
        </Card>
      )}
    </div>
  );
}

