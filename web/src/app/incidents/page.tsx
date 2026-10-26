import { IncidentList } from "@/components/incident-list";

export default function IncidentsPage() {
  return (
    <>
      <h1 className="mb-1 text-xl font-semibold">Incidents</h1>
      <p className="mb-6 text-sm text-ink-2">
        Opened by the anomaly detector. New incidents and changes appear here live.
      </p>
      <IncidentList />
    </>
  );
}
