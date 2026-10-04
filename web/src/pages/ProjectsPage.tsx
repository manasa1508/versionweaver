import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Boxes, GitBranch, Plus, Search } from "lucide-react";
import { useState, type FormEvent } from "react";
import { EmptyState, ErrorState, LoadingState, Modal, PageHeader } from "../components/Common";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, shortId } from "../lib/format";

export function ProjectsPage() {
  const { controlToken } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [sourceUri, setSourceUri] = useState("");
  const [branch, setBranch] = useState("main");
  const projects = useInfiniteQuery({
    queryKey: ["projects", search],
    queryFn: ({ pageParam }) => api.projects(controlToken, search, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.nextCursor
  });
  const createProject = useMutation({
    mutationFn: () => api.createProject(controlToken, { name, source_uri: sourceUri, default_branch: branch }),
    onSuccess: async () => {
      setCreating(false); setName(""); setSourceUri(""); setBranch("main");
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      await queryClient.invalidateQueries({ queryKey: ["summary"] });
    }
  });

  const items = projects.data?.pages.flatMap((page) => page.items) ?? [];
  function submit(event: FormEvent) { event.preventDefault(); createProject.mutate(); }

  return (
    <>
      <PageHeader eyebrow="Source inventory" title="Projects" description="Register repositories and inspect the inventory that informs each migration plan." actions={<button className="button button-primary" type="button" onClick={() => setCreating(true)}><Plus size={17} />Register project</button>} />
      <div className="toolbar"><label className="search-field"><Search size={17} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search projects" aria-label="Search projects" /></label><span>{items.length} loaded</span></div>
      {projects.isPending ? <LoadingState label="Loading projects" /> : projects.isError ? <ErrorState error={projects.error} retry={() => projects.refetch()} /> : items.length ? (
        <section className="project-grid">{items.map((project) => {
          const inventoryCount = project.inventory ? Object.keys(project.inventory).length : 0;
          return <article className="project-card" key={project.id}><div className="project-card-top"><div className="project-icon"><Boxes size={21} /></div><span className="mono-id">{shortId(project.id)}</span></div><h2>{project.name}</h2><p title={project.source_uri}>{project.source_uri}</p><div className="project-meta"><span><GitBranch size={15} />{project.default_branch}</span><span>{inventoryCount ? `${inventoryCount} inventory groups` : "Inventory pending"}</span></div><footer><span>Updated {formatDate(project.updated_at)}</span></footer></article>;
        })}</section>
      ) : <EmptyState title="No matching projects" body="Register a repository to begin dependency and model discovery." action={<button className="button button-primary" type="button" onClick={() => setCreating(true)}>Register project</button>} />}
      {projects.hasNextPage && <div className="load-more"><button className="button button-secondary" type="button" disabled={projects.isFetchingNextPage} onClick={() => projects.fetchNextPage()}>{projects.isFetchingNextPage ? "Loading…" : "Load more projects"}</button></div>}
      {creating && <Modal title="Register a project" onClose={() => setCreating(false)}><form className="modal-form" onSubmit={submit}><label>Project name<input required minLength={2} pattern="[A-Za-z0-9][A-Za-z0-9_.-]+" value={name} onChange={(event) => setName(event.target.value)} placeholder="payments-api" /></label><label>Source URI<input required value={sourceUri} onChange={(event) => setSourceUri(event.target.value)} placeholder="https://github.com/acme/payments-api.git" /></label><label>Default branch<input required value={branch} onChange={(event) => setBranch(event.target.value)} /></label>{createProject.isError && <div className="form-error">{createProject.error.message}</div>}<div className="modal-actions"><button className="button button-secondary" type="button" onClick={() => setCreating(false)}>Cancel</button><button className="button button-primary" type="submit" disabled={createProject.isPending}>{createProject.isPending ? "Registering…" : "Register project"}</button></div></form></Modal>}
    </>
  );
}
