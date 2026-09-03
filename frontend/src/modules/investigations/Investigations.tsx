import { Link, useParams } from "react-router-dom";
import { InvestigationsList } from "./InvestigationsList";

export default function Investigations() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  return (
    <InvestigationsList
      projectId={projectId}
      title="Vajra Investigations"
      description="Signal → Candidate → Investigation → Evidence → Validation → Finding. Every investigation here started from something Vajra or you flagged as worth a closer look."
      emptyMessage="No investigations yet. Start one from an Analyzer finding, a Diff result, a high-priority asset, or create one manually below."
      showNewButton
      headerExtra={
        <Link to={`/projects/${projectId}/findings`} className="text-xs text-vajra-accent2 hover:underline">
          View Findings (validated only) →
        </Link>
      }
    />
  );
}
