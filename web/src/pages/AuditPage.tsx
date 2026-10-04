import { useInfiniteQuery } from "@tanstack/react-query";
import { FileClock, KeyRound } from "lucide-react";
import { Link } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState, PageHeader } from "../components/Common";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, shortId, titleCase } from "../lib/format";

export function AuditPage() {
  const { adminToken } = useAuth();
  const events = useInfiniteQuery({
    queryKey: ["audit"],
    queryFn: ({ pageParam }) => api.audit(adminToken, undefined, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.nextCursor,
    enabled: Boolean(adminToken),
    refetchInterval: 20_000
  });
  const items = events.data?.pages.flatMap((page) => page.items) ?? [];
  return <>
    <PageHeader eyebrow="Append-only accountability" title="Audit trail" description="Review who initiated, approved, leased, cancelled, and completed every governed change." />
    {!adminToken ? <EmptyState title="Admin access required" body="Add an admin-scoped token in Connection settings to read the audit ledger." action={<Link className="button button-primary" to="/settings"><KeyRound size={17} />Configure admin token</Link>} /> : events.isPending ? <LoadingState label="Loading audit events" /> : events.isError ? <ErrorState error={events.error} retry={() => events.refetch()} /> : items.length ? <section className="audit-timeline">{items.map((event) => <article key={event.id}><div className="timeline-marker"><FileClock size={16} /></div><div className="timeline-card"><header><div><strong>{titleCase(event.action)}</strong><span>{formatDate(event.created_at)}</span></div><span className="actor-chip">{event.actor}</span></header>{event.change_id && <Link to={`/changes/${event.change_id}`}>Change {shortId(event.change_id)}</Link>}<pre>{JSON.stringify(event.details, null, 2)}</pre></div></article>)}</section> : <EmptyState title="No audit events" body="Governed workflow activity will appear here." />}
    {events.hasNextPage && <div className="load-more"><button className="button button-secondary" type="button" onClick={() => events.fetchNextPage()} disabled={events.isFetchingNextPage}>{events.isFetchingNextPage ? "Loading…" : "Load older events"}</button></div>}
  </>;
}
