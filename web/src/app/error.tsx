"use client";

import { useEffect } from "react";

import { ErrorPanel } from "@/components/states";

// Last-resort boundary: catches unexpected rendering errors anywhere below the root layout,
// so a bug shows a message with a retry button instead of a blank page.
export default function RootError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  return <ErrorPanel message="Something went wrong while showing this page." onRetry={retry} />;
}
