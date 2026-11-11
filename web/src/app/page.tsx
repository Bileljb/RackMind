import { RackGrid } from "@/components/rack-grid";

// A Server Component: the heading is rendered on the server (static HTML), the live grid
// is a Client Component that fetches and polls in the browser.
export default function RacksPage() {
  return (
    <>
      <h1 className="mb-1 text-xl font-semibold">Racks</h1>
      <p className="mb-6 text-sm text-ink-2">
        Every server at a glance (CPU temperature, or CPU usage when a server has no sensor),
        refreshed every 5 seconds.
      </p>
      <RackGrid />
    </>
  );
}
