import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Box, ChevronRight, Filter, Plus, Search } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState, Modal, PageHeader } from "../components/Common";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, riskLabel, shortId, titleCase } from "../lib/format";
import type { ChangeInput } from "../types";

const statuses = ["planned", "queued", "running", "verifying", "succeeded", "failed", "blocked", "cancelled"];

export function ChangesPage() {
  const { controlToken, actor } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(params.get("create") === "true");
  const search = params.get("search") ?? "";
  const status = params.get("status") ?? "";
  const kind = params.get("kind") ?? "";
  useEffect(() => { if (params.get("create") === "true") setCreating(true); }, [params]);
  const filters = { search, status, kind };
  const changes = useInfiniteQuery({
    queryKey: ["changes", filters],
    queryFn: ({ pageParam }) => api.changes(controlToken, filters, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.nextCursor
  });
  const projects = useQuery({ queryKey: ["projects", "selector"], queryFn: () => api.projects(controlToken) });
  const create = useMutation({
    mutationFn: (input: ChangeInput) => api.createChange(controlToken, input),
    onSuccess: async (change) => {
      await queryClient.invalidateQueries({ queryKey: ["changes"] });
      await queryClient.invalidateQueries({ queryKey: ["summary"] });
      navigate(`/changes/${change.id}`);
    }
  });
  const items = changes.data?.pages.flatMap((page) => page.items) ?? [];
  const projectMap = new Map((projects.data?.items ?? []).map((project) => [project.id, project.name]));
  function update(key: string, value: string) { const next = new URLSearchParams(params); value ? next.set(key, value) : next.delete(key); next.delete("create"); setParams(next); }

  return (
    <>
      <PageHeader eyebrow="Governed change workflow" title="Migration changes" description="Move dependency and AI model upgrades from risk assessment through verified evidence." actions={<button className="button button-primary" type="button" onClick={() => setCreating(true)}><Plus size={17} />Plan change</button>} />
      <div className="toolbar filter-toolbar"><label className="search-field"><Search size={17} /><input value={search} onChange={(event) => update("search", event.target.value)} placeholder="Search change titles" /></label><div className="filter-group"><Filter size={16} /><select value={kind} onChange={(event) => update("kind", event.target.value)} aria-label="Filter by kind"><option value="">All kinds</option><option value="dependency">Dependency</option><option value="model">AI model</option></select><select value={status} onChange={(event) => update("status", event.target.value)} aria-label="Filter by status"><option value="">All statuses</option>{statuses.map((value) => <option value={value} key={value}>{titleCase(value)}</option>)}</select></div></div>
      {changes.isPending ? <LoadingState label="Loading migration changes" /> : changes.isError ? <ErrorState error={changes.error} retry={() => changes.refetch()} /> : items.length ? <div className="table-wrap"><table className="data-table"><thead><tr><th>Change</th><th>Project</th><th>Risk</th><th>Status</th><th>Updated</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>{items.map((change) => <tr key={change.id} onClick={() => navigate(`/changes/${change.id}`)}><td><div className="table-primary"><span className={`kind-glyph ${change.kind === "model" ? "model" : ""}`}>{change.kind === "model" ? <Bot size={16} /> : <Box size={16} />}</span><div><strong>{change.title}</strong><span>{titleCase(change.kind)} · {shortId(change.id)}</span></div></div></td><td>{projectMap.get(change.project_id) ?? shortId(change.project_id)}</td><td><span className={`risk-chip risk-${riskLabel(change.risk_score)}`}>{change.risk_score} · {titleCase(riskLabel(change.risk_score))}</span></td><td><StatusBadge value={change.status} /></td><td>{formatDate(change.updated_at)}</td><td><ChevronRight size={17} /></td></tr>)}</tbody></table></div> : <EmptyState title="No changes found" body="Adjust the filters or create a migration plan." action={<button className="button button-primary" type="button" onClick={() => setCreating(true)}>Plan a change</button>} />}
      {changes.hasNextPage && <div className="load-more"><button className="button button-secondary" type="button" disabled={changes.isFetchingNextPage} onClick={() => changes.fetchNextPage()}>{changes.isFetchingNextPage ? "Loading…" : "Load more changes"}</button></div>}
      {creating && <CreateChangeModal projects={projects.data?.items ?? []} actor={actor} pending={create.isPending} error={create.error} onSubmit={(input) => create.mutate(input)} onClose={() => { setCreating(false); const next = new URLSearchParams(params); next.delete("create"); setParams(next, { replace: true }); }} />}
    </>
  );
}

function CreateChangeModal({ projects, actor, pending, error, onSubmit, onClose }: { projects: Array<{ id: string; name: string }>; actor: string; pending: boolean; error: Error | null; onSubmit: (input: ChangeInput) => void; onClose: () => void }) {
  const [projectId, setProjectId] = useState(projects[0]?.id ?? "");
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<"dependency" | "model">("dependency");
  const [subject, setSubject] = useState("");
  const [fromValue, setFromValue] = useState("");
  const [toValue, setToValue] = useState("");
  const [commands, setCommands] = useState("python -m compileall -q .");
  const [timeout, setTimeoutValue] = useState(600);
  const [allowNetwork, setAllowNetwork] = useState(false);
  useEffect(() => {
    if (!projectId && projects[0]) setProjectId(projects[0].id);
  }, [projectId, projects]);
  function submit(event: FormEvent) {
    event.preventDefault();
    const verificationCommands = commands.split("\n").map((item) => item.trim()).filter(Boolean);
    const spec = kind === "dependency" ? { kind, dependency_name: subject, from_version: fromValue || null, to_version: toValue, verification_commands: verificationCommands, timeout_seconds: timeout, allow_network: allowNetwork } : { kind, from_model: fromValue, to_model: toValue, from_provider: subject || null, verification_commands: verificationCommands, timeout_seconds: timeout, allow_network: allowNetwork, evaluation_cases: [] };
    onSubmit({ project_id: projectId, title, requested_by: actor, spec });
  }
  return <Modal title="Plan a migration" onClose={onClose}><form className="modal-form change-form" onSubmit={submit}><div className="segmented"><button type="button" className={kind === "dependency" ? "active" : ""} onClick={() => setKind("dependency")}><Box size={16} />Dependency</button><button type="button" className={kind === "model" ? "active" : ""} onClick={() => setKind("model")}><Bot size={16} />AI model</button></div><label>Project<select required value={projectId} onChange={(event) => setProjectId(event.target.value)}><option value="" disabled>Select a project</option>{projects.map((project) => <option value={project.id} key={project.id}>{project.name}</option>)}</select></label><label>Change title<input required minLength={3} value={title} onChange={(event) => setTitle(event.target.value)} placeholder={kind === "dependency" ? "Upgrade Pydantic to 2.10" : "Move support agent to llama3.3"} /></label><div className="form-row"><label>{kind === "dependency" ? "Dependency" : "Provider (optional)"}<input required={kind === "dependency"} value={subject} onChange={(event) => setSubject(event.target.value)} placeholder={kind === "dependency" ? "pydantic" : "ollama"} /></label><label>Current {kind === "dependency" ? "version" : "model"}<input required={kind === "model"} value={fromValue} onChange={(event) => setFromValue(event.target.value)} placeholder={kind === "dependency" ? "2.9.0" : "llama3.1"} /></label><label>Target {kind === "dependency" ? "version" : "model"}<input required value={toValue} onChange={(event) => setToValue(event.target.value)} placeholder={kind === "dependency" ? "2.10.0" : "llama3.3"} /></label></div><label>Verification commands<span>One shell command per line, executed inside the isolated sandbox.</span><textarea rows={3} value={commands} onChange={(event) => setCommands(event.target.value)} /></label><div className="form-row compact"><label>Timeout (seconds)<input type="number" min={10} max={7200} value={timeout} onChange={(event) => setTimeoutValue(Number(event.target.value))} /></label><label className="checkbox-label"><input type="checkbox" checked={allowNetwork} onChange={(event) => setAllowNetwork(event.target.checked)} /><span>Allow sandbox network <small>Only enable when verification requires external services.</small></span></label></div>{error && <div className="form-error">{error.message}</div>}<div className="modal-actions"><button className="button button-secondary" type="button" onClick={onClose}>Cancel</button><button className="button button-primary" disabled={pending || !projects.length} type="submit">{pending ? "Assessing risk…" : "Create plan"}</button></div></form></Modal>;
}
