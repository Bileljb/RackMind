import Link from "next/link";

export default function NotFound() {
  return (
    <div className="rounded-lg border border-line bg-surface p-6 text-sm">
      <h1 className="font-medium">Page not found</h1>
      <Link href="/" className="mt-3 inline-block text-ink-2 underline hover:text-ink">
        Back to racks
      </Link>
    </div>
  );
}
