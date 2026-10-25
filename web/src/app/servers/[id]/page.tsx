import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ServerDetail } from "@/components/server-detail";
import { Skeleton } from "@/components/states";

// `params` is only known at request time, so reading it happens inside <Suspense>:
// Next.js serves the static shell (the fallback) instantly and streams the rest in.
export default function ServerPage({ params }: PageProps<"/servers/[id]">) {
  return (
    <Suspense fallback={<Skeleton className="h-96" />}>
      <ServerDetailForParams params={params} />
    </Suspense>
  );
}

async function ServerDetailForParams({ params }: Pick<PageProps<"/servers/[id]">, "params">) {
  const { id } = await params;
  const serverId = Number(id);
  if (!Number.isInteger(serverId) || serverId <= 0) notFound();
  return <ServerDetail serverId={serverId} />;
}
