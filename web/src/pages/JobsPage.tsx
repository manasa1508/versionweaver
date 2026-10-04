import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { AlertOctagon, ChevronRight, CircleGauge, Filter } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, shortId, titleCase } from "../lib/format";

const jobStatuses = ["queued", "leased", "running", "succeeded", "failed", "dead_letter", "cancelled"];

export function JobsPage() {
  const { controlToken } = useAuth();
  const navigate = useNavigate();
  const [status, setStatus] = useState("");
  const jobs = useInfiniteQuery({
    queryKey: ["jobs", status],
    queryFn: ({ pageParam }) => api.jobs(controlToken, status, undefined, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.nextCursor,
    refetchInterval: 15_000
  });
  const summary = useQuery({ queryKey: ["summary"], queryFn: () => api.summary(controlToken), refetchInterval: 15_000 });
  const items = jobs.data?.pages.flatMap((page) => page.items) ?? [];

  return <>
    <PageHeader eyebrow="Durable execution" title="Job queue" description="Observe leases, retries, worker ownership, and exhausted jobs without touching runner credentials." />
    <section className="queue-summary"><div><CircleGauge size={19} /><span>Active queue</span><strong>{summary.data?.queue_depth ?? "—"}</strong></div><div><AlertOctagon size={19} /><span>Dead-lettered</span><strong>{summary.data?.dead_letter_count ?? "—"}</strong></div><div><span className="attempt-symbol">↻</span><span>Delivery model</span><strong>At least once</strong></div></section>
    <div className="toolbar"><div className="filter-group"><Filter size={16} /><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All job statuses</option>{jobStatuses.map((value) => <option value={value} key={value}>{titleCase(value)}</option>)}</select></div><span>Refreshes every 15 seconds</span></div>
    {jobs.isPending ? <LoadingState label="Loading execution queue" /> : jobs.isError ? <ErrorState error={jobs.error} retry={() => jobs.refetch()} /> : items.length ? <div className="table-wrap"><table className="data-table jobs-table"><thead><tr><th>Job</th><th>Status</th><th>Attempts</th><th>Lease owner</th><th>Lease expires</th><th>Updated</th><th /></tr></thead><tbody>{items.map((job) => <tr key={job.id} onClick={() => navigate(`/changes/${job.change_id}`)} className={job.status === "dead_letter" ? "alert-row" : ""}><td><div><strong className="mono-id">{shortId(job.id)}</strong><span>Change {shortId(job.change_id)}</span></div></td><td><StatusBadge value={job.status} /></td><td><div className="attempt-meter"><span>{job.attempts}/{job.max_attempts}</span><div><i style={{ width: `${(job.attempts / job.max_attempts) * 100}%` }} /></div></div></td><td>{job.lease_owner ?? "—"}</td><td>{formatDate(job.lease_expires_at)}</td><td>{formatDate(job.updated_at)}</td><td><ChevronRight size={17} /></td></tr>)}</tbody></table></div> : <EmptyState title="No jobs in this view" body="Jobs are created atomically when a migration plan is approved." />}
    {jobs.hasNextPage && <div className="load-more"><button className="button button-secondary" type="button" onClick={() => jobs.fetchNextPage()} disabled={jobs.isFetchingNextPage}>{jobs.isFetchingNextPage ? "Loading…" : "Load more jobs"}</button></div>}
  </>;
}
