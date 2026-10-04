import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowUpRight, CheckCircle2, CircleGauge, FileCheck2, GitPullRequestArrow, Layers3, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { shortId, timeAgo, titleCase } from "../lib/format";

export function OverviewPage() {
  const { controlToken, adminToken } = useAuth();
  const summary = useQuery({ queryKey: ["summary"], queryFn: () => api.summary(controlToken), refetchInterval: 15_000 });
  const changes = useQuery({ queryKey: ["changes", "recent"], queryFn: () => api.changes(controlToken), refetchInterval: 15_000 });
  const jobs = useQuery({ queryKey: ["jobs", "recent"], queryFn: () => api.jobs(controlToken), refetchInterval: 15_000 });
  const audit = useQuery({ queryKey: ["audit", "recent"], queryFn: () => api.audit(adminToken), enabled: Boolean(adminToken), refetchInterval: 20_000 });

  if (summary.isPending) return <LoadingState />;
  if (summary.isError) return <ErrorState error={summary.error} retry={() => summary.refetch()} />;
  const data = summary.data;
  const recentChanges = changes.data?.items.slice(0, 5) ?? [];
  const statusTotal = Math.max(data.change_count, 1);
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  return (
    <>
      <PageHeader eyebrow="Live migration posture" title={`${greeting}, operator.`} description="Track change safety, queue pressure, and verification outcomes across the entire workspace." actions={<Link className="button button-primary" to="/changes?create=true">Plan a migration <ArrowUpRight size={17} /></Link>} />
      <section className="metric-grid">
        <article className="metric-card accent-card"><div className="metric-icon"><Layers3 size={19} /></div><span>Managed projects</span><strong>{data.project_count}</strong><small>{data.change_count} total changes</small></article>
        <article className="metric-card"><div className="metric-icon violet"><GitPullRequestArrow size={19} /></div><span>Active changes</span><strong>{data.active_change_count}</strong><small>{data.changes_by_status.planned ?? 0} awaiting approval</small></article>
        <article className="metric-card"><div className="metric-icon green"><CheckCircle2 size={19} /></div><span>Verification success</span><strong>{data.success_rate.toFixed(1)}%</strong><small>{data.evidence_count} evidence bundles</small></article>
        <article className={`metric-card ${data.dead_letter_count ? "danger-card" : ""}`}><div className="metric-icon amber"><CircleGauge size={19} /></div><span>Queue depth</span><strong>{data.queue_depth}</strong><small>{data.dead_letter_count} dead-lettered</small></article>
      </section>

      <section className="dashboard-grid">
        <article className="panel status-panel">
          <div className="panel-heading"><div><p className="eyebrow">Change distribution</p><h2>Migration pipeline</h2></div><Activity size={20} /></div>
          <div className="status-stack">
            {Object.entries(data.changes_by_status).sort((a, b) => b[1] - a[1]).map(([status, count]) => (
              <div className="status-row" key={status}><div><StatusBadge value={status} /><span>{count}</span></div><div className="status-track"><span style={{ width: `${Math.max((count / statusTotal) * 100, 3)}%` }} /></div></div>
            ))}
            {!Object.keys(data.changes_by_status).length && <EmptyState title="No changes yet" body="Create the first migration plan to populate this pipeline." />}
          </div>
        </article>
        <article className="panel signal-panel">
          <div className="panel-heading"><div><p className="eyebrow">Reliability signals</p><h2>Control-plane health</h2></div><ShieldAlert size={20} /></div>
          <div className="signal-list">
            <div><span className={data.dead_letter_count ? "signal-dot danger" : "signal-dot good"} /><div><strong>Dead-letter queue</strong><p>{data.dead_letter_count ? `${data.dead_letter_count} job needs operator attention` : "No exhausted execution jobs"}</p></div><b>{data.dead_letter_count}</b></div>
            <div><span className={data.unpublished_event_count ? "signal-dot warn" : "signal-dot good"} /><div><strong>Integration outbox</strong><p>{data.unpublished_event_count ? "Events are waiting for dispatch" : "All domain events published"}</p></div><b>{data.unpublished_event_count}</b></div>
            <div><span className="signal-dot good" /><div><strong>Evidence integrity</strong><p>Content-addressed SHA-256 bundles</p></div><FileCheck2 size={18} /></div>
          </div>
        </article>
      </section>

      <section className="dashboard-grid lower-grid">
        <article className="panel table-panel">
          <div className="panel-heading"><div><p className="eyebrow">Recently updated</p><h2>Changes</h2></div><Link to="/changes">View all <ArrowUpRight size={14} /></Link></div>
          {recentChanges.length ? <div className="compact-list">{recentChanges.map((change) => <Link to={`/changes/${change.id}`} key={change.id}><div className="kind-glyph">{change.kind === "model" ? "AI" : "DP"}</div><div className="compact-main"><strong>{change.title}</strong><span>{titleCase(change.kind)} · {shortId(change.id)}</span></div><StatusBadge value={change.status} /><time>{timeAgo(change.updated_at)}</time></Link>)}</div> : <EmptyState title="Nothing in flight" body="Planned dependency and model changes will appear here." />}
        </article>
        <article className="panel table-panel">
          <div className="panel-heading"><div><p className="eyebrow">Latest execution</p><h2>Job activity</h2></div><Link to="/jobs">View queue <ArrowUpRight size={14} /></Link></div>
          <div className="compact-list jobs-compact">{(jobs.data?.items.slice(0, 5) ?? []).map((job) => <Link to={`/changes/${job.change_id}`} key={job.id}><div className="kind-glyph job-glyph">{job.attempts}</div><div className="compact-main"><strong>Job {shortId(job.id)}</strong><span>Change {shortId(job.change_id)} · attempt {job.attempts}/{job.max_attempts}</span></div><StatusBadge value={job.status} /><time>{timeAgo(job.updated_at)}</time></Link>)}</div>
          {!jobs.data?.items.length && <EmptyState title="Queue is empty" body="Approved changes create durable execution jobs." />}
        </article>
      </section>

      {adminToken && audit.data?.items.length ? <section className="panel audit-strip"><div><p className="eyebrow">Latest audit event</p><strong>{titleCase(audit.data.items[0]!.action)}</strong><span> by {audit.data.items[0]!.actor} · {timeAgo(audit.data.items[0]!.created_at)}</span></div><Link to="/audit">Open immutable trail <ArrowUpRight size={15} /></Link></section> : null}
    </>
  );
}
