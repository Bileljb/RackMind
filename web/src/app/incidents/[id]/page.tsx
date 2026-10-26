import { notFound } from "next/navigation";
import { Suspense } from "react";

import { IncidentDetailView } from "@/components/incident-detail";
import { Skeleton } from "@/components/states";

// Same pattern as the server page: `params` is read inside <Suspense>.
export default function IncidentPage({ params }: PageProps<"/incidents/[id]">) {
  return (
    <Suspense fallback={<Skeleton className="h-96" />}>
      <IncidentForParams params={params} />
    </Suspense>
  );
}

async function IncidentForParams({ params }: Pick<PageProps<"/incidents/[id]">, "params">) {
  const { id } = await params;
  const incidentId = Number(id);
  if (!Number.isInteger(incidentId) || incidentId <= 0) notFound();
  return <IncidentDetailView incidentId={incidentId} />;
}
