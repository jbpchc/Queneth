"use client";

import { useQuery } from "@tanstack/react-query";
import { Database, Plug, Server } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { api, toApiError, type ApiSchemas } from "@/lib/api/client";

type HealthResponse = ApiSchemas["HealthResponse"];

/** Live API health, demonstrating loading / error / success states end to end. */
export function SystemStatus() {
  const query = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      // 503 still returns a HealthResponse body, so read data or error alike.
      const { data, error, response } = await api.GET("/api/v1/health");
      const body: HealthResponse | undefined =
        data ?? (response.status === 503 ? (error as unknown as HealthResponse) : undefined);
      if (!body) throw error ?? new Error("No response");
      return body;
    },
    retry: false,
  });

  if (query.isPending) {
    return (
      <Card aria-busy="true" aria-label="Checking system status">
        <CardContent className="flex flex-col gap-4">
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-11 w-full" />
          <Skeleton className="h-11 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (query.isError) {
    return (
      <ErrorState
        title="API unreachable"
        message={`${toApiError(query.error).message} Start the backend with docker compose up.`}
        onRetry={() => query.refetch()}
      />
    );
  }

  const h = query.data;
  const rows = [
    { icon: Server, label: "API", value: `v${h.version} · ${h.environment}`, ok: true },
    { icon: Database, label: "Database", value: h.database, ok: h.database === "ok" },
    { icon: Plug, label: "Integrations", value: `${h.integrations_mode} mode`, ok: true },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>System status</CardTitle>
        <CardDescription>Live from the Python API.</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col divide-y divide-border">
          {rows.map(({ icon: Icon, label, value, ok }) => (
            <li key={label} className="flex min-h-12 items-center gap-3">
              <Icon aria-hidden className="size-4 text-ink-muted" />
              <span className="flex-1 text-small font-semibold text-ink">{label}</span>
              <Badge tone={ok ? "success" : "danger"}>{value}</Badge>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
