import { Link, useParams } from "react-router-dom";
import { CaseDetailView } from "../components/CaseDetailView";

export function CaseDetailPage() {
  const { id } = useParams();
  const caseId = Number(id);
  return (
    <div className="space-y-3">
      <Link to="/cases" className="text-xs text-beam hover:underline">← Back to cases</Link>
      {Number.isFinite(caseId) ? <CaseDetailView caseId={caseId} /> : <p className="text-sm text-sev-serious">Invalid case id.</p>}
    </div>
  );
}
