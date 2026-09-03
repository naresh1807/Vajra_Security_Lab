import { useParams } from "react-router-dom";
import { InvestigationsList } from "./InvestigationsList";

export default function Findings() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  return (
    <InvestigationsList
      projectId={projectId}
      title="Vajra Findings"
      description="Investigations you've validated - ready to move toward a report. This is a filtered view of Investigations, not a separate record: mark an investigation Validated there to see it here."
      statusFilter="validated"
      emptyMessage="No validated findings yet. Open an investigation and mark it Validated once you've confirmed it with evidence."
    />
  );
}
