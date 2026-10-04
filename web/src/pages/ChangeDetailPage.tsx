import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, FileCheck2, GitBranch, ShieldAlert, StopCircle, X } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ErrorState, LoadingState, Modal } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, riskLabel, shortId, titleCase } from "../lib/format";
import type { Evidence } from "../types";

export function ChangeDetailPage() {
  const { changeId = "" } = useParams();
  const { controlToken, adminToken, actor } = useAuth();
  const queryClient = useQueryClient();
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);
  const change = useQuery({ queryKey: ["change", changeId], queryFn: () => api.change(controlToken, changeId), refetchInterval: 10_000 });
  const project = useQuery({ queryKey: ["project", change.data?.project_id], queryFn: () => api.project(controlToken, change.data!.project_id), enabled: Boolean(change.data?.project_id) });
  const evidence = useQuery({ queryKey: ["evidence", changeId], queryFn: () => api.evidence(controlToken, changeId), enabled: Boolean(changeId), refetchInterval: 15_000 });
  const jobs = useQuery({ queryKey: ["jobs", "change", changeId], queryFn: () => api.jobs(controlToken, undefined, changeId), enabled: Boolean(changeId), refetchInterval: 10_000 });
  const audit = useQuery({ queryKey: ["audit", "change", changeId], queryFn: () => api.audit(adminToken, changeId), enabled: Boolean(adminToken && changeId) });
  const approve = useMutation({ mutationFn: () => api.approveChange(controlToken, change.data!, actor), onSuccess: refresh });
  const cancel = useMutation({ mutationFn: () => api.cancelChange(controlToken, change.data!, actor, cancelReason), onSuccess: async () => { setCancelOpen(false); await refresh(); } });
  async function refresh() { await Promise.all([queryClient.invalidateQueries({ queryKey: ["change", changeId] }), queryClient.invalidateQueries({ queryKey: ["changes"] }), queryClient.invalidateQueries({ queryKey: ["jobs"] }), queryClient.invalidateQueries({ queryKey: ["summary"] })]); }

  if (change.isPending) return <LoadingState label="Loading change details" />;
  if (change.isError) return <ErrorState error={change.error} retry={() => change.refetch()} />;
  const item = change.data;
  const canApprove = item.status === "planned";
  const canCancel = ["planned", "approved", "queued", "running", "verifying"].includes(item.status);
  const detailPairs = Object.entries(item.spec).filter(([, value]) => value !== null && value !== "" && (!Array.isArray(value) || value.length));

  return <>
    <Link className="back-link" to="/changes"><ArrowLeft size={16} />All changes</Link>
    <header className="detail-header"><div><div className="detail-kicker"><span>{titleCase(item.kind)} migration</span><span>·</span><span className="mono-id">{shortId(item.id)}</span></div><h1>{item.title}</h1><div className="detail-meta"><StatusBadge value={item.status} /><span><GitBranch size={14} />{project.data?.name ?? shortId(item.project_id)}</span><span>Requested by {item.requested_by}</span></div></div><div className="header-actions">{canCancel && <button className="button button-danger-ghost" type="button" onClick={() => setCancelOpen(true)}><StopCircle size={17} />Cancel</button>}{canApprove && <button className="button button-primary" type="button" disabled={approve.isPending} onClick={() => approve.mutate()}><Check size={17} />{approve.isPending ? "Approving…" : "Approve & queue"}</button>}</div></header>
    {(approve.isError || cancel.isError) && <div className="form-error detail-error">{(approve.error ?? cancel.error)?.message}</div>}
    <section className="detail-grid">
      <article className="panel detail-main"><div className="panel-heading"><div><p className="eyebrow">Change contract</p><h2>Migration specification</h2></div></div><dl className="spec-grid">{detailPairs.map(([key, value]) => <div key={key}><dt>{titleCase(key)}</dt><dd>{typeof value === "object" ? <pre>{JSON.stringify(value, null, 2)}</pre> : String(value)}</dd></div>)}</dl></article>
      <aside className="detail-aside"><article className="panel risk-panel"><div className={`risk-score risk-${riskLabel(item.risk_score)}`}><ShieldAlert size={20} /><strong>{item.risk_score}</strong><span>{titleCase(riskLabel(item.risk_score))} risk</span></div><h3>Deterministic assessment</h3>{item.risk_reasons.length ? <ul>{item.risk_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : <p>No elevated risk factors detected.</p>}<footer>Version {item.version} · updated {formatDate(item.updated_at)}</footer></article><article className="panel ownership-panel"><p className="eyebrow">Governance</p><dl><div><dt>Requested by</dt><dd>{item.requested_by}</dd></div><div><dt>Approved by</dt><dd>{item.approved_by ?? "Pending"}</dd></div><div><dt>Approved at</dt><dd>{formatDate(item.approved_at)}</dd></div></dl></article></aside>
    </section>
    <section className="panel detail-section"><div className="panel-heading"><div><p className="eyebrow">Durable execution</p><h2>Job attempts</h2></div></div>{jobs.data?.items.length ? <div className="attempt-cards">{jobs.data.items.map((job) => <div key={job.id}><div><strong>Job {shortId(job.id)}</strong><StatusBadge value={job.status} /></div><span>Attempt {job.attempts} of {job.max_attempts}</span><span>Runner: {job.lease_owner ?? "unassigned"}</span><span>Lease: {formatDate(job.lease_expires_at)}</span>{job.last_error && <p>{job.last_error}</p>}</div>)}</div> : <p className="muted">Approval creates the first durable execution job.</p>}</section>
    <section className="panel detail-section"><div className="panel-heading"><div><p className="eyebrow">Verification record</p><h2>Evidence bundles</h2></div><FileCheck2 size={20} /></div>{evidence.data?.length ? <div className="evidence-grid">{evidence.data.map((record) => <button key={record.id} type="button" onClick={() => setSelectedEvidence(record)}><FileCheck2 size={19} /><div><strong>{titleCase(record.kind)}</strong><span>{formatDate(record.created_at)}</span><code>sha256:{record.sha256.slice(0, 16)}…</code></div></button>)}</div> : <p className="muted">Evidence appears after runner verification completes.</p>}</section>
    {adminToken && audit.data?.items.length ? <section className="panel detail-section"><div className="panel-heading"><div><p className="eyebrow">Traceability</p><h2>Change history</h2></div></div><div className="mini-timeline">{audit.data.items.map((event) => <div key={event.id}><span /><div><strong>{titleCase(event.action)}</strong><p>{event.actor} · {formatDate(event.created_at)}</p></div></div>)}</div></section> : null}
    {cancelOpen && <Modal title="Cancel this change" onClose={() => setCancelOpen(false)}><form className="modal-form" onSubmit={(event) => { event.preventDefault(); cancel.mutate(); }}><p>Cancellation is recorded in the audit trail and prevents future execution. An active runner may finish its current sandbox command before observing cancellation.</p><label>Reason<textarea required minLength={3} rows={4} value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} placeholder="Why is this migration being cancelled?" /></label><div className="modal-actions"><button className="button button-secondary" type="button" onClick={() => setCancelOpen(false)}>Keep change</button><button className="button button-danger" type="submit" disabled={cancel.isPending}>{cancel.isPending ? "Cancelling…" : "Confirm cancellation"}</button></div></form></Modal>}
    {selectedEvidence && <EvidenceModal record={selectedEvidence} token={controlToken} onClose={() => setSelectedEvidence(null)} />}
  </>;
}

function EvidenceModal({ record, token, onClose }: { record: Evidence; token: string; onClose: () => void }) {
  const content = useQuery({ queryKey: ["evidence-content", record.id], queryFn: () => api.evidenceContent(token, record.id) });
  return <div className="modal-backdrop" role="presentation" onMouseDown={onClose}><section className="modal evidence-modal" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}><header><div><p className="eyebrow">Immutable evidence</p><h2>{titleCase(record.kind)}</h2></div><button className="icon-button" type="button" onClick={onClose}><X size={20} /></button></header><div className="evidence-hash"><span>SHA-256</span><code>{record.sha256}</code></div>{content.isPending ? <LoadingState /> : content.isError ? <ErrorState error={content.error} /> : <pre className="json-view">{JSON.stringify(content.data, null, 2)}</pre>}</section></div>;
}
