import { Save, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { PageHeader } from "../components/Common";
import { useAuth } from "../context/AuthContext";

export function SettingsPage() {
  const auth = useAuth();
  const [apiUrl, setApiUrl] = useState(auth.apiUrl);
  const [controlToken, setControlToken] = useState(auth.controlToken);
  const [adminToken, setAdminToken] = useState(auth.adminToken);
  const [actor, setActor] = useState(auth.actor);
  const [saved, setSaved] = useState(false);

  function submit(event: FormEvent) {
    event.preventDefault();
    auth.save({ apiUrl, controlToken, adminToken, actor });
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2500);
  }

  return (
    <>
      <PageHeader eyebrow="Workspace security" title="Connection settings" description="Manage the API endpoint and role-scoped credentials used by this browser tab." />
      <div className="settings-grid">
        <form className="panel settings-form" onSubmit={submit}>
          <label>API URL<input value={apiUrl} onChange={(event) => setApiUrl(event.target.value)} placeholder="Same origin" /></label>
          <label>Developer token<input type="password" autoComplete="new-password" value={controlToken} onChange={(event) => setControlToken(event.target.value)} /></label>
          <label>Admin token <em>optional</em><input type="password" autoComplete="new-password" value={adminToken} onChange={(event) => setAdminToken(event.target.value)} /></label>
          <label>Audit identity<input value={actor} onChange={(event) => setActor(event.target.value)} /></label>
          <button className="button button-primary" type="submit"><Save size={17} />{saved ? "Saved" : "Save connection"}</button>
        </form>
        <aside className="panel security-explainer">
          <div className="section-icon"><ShieldCheck size={22} /></div>
          <h3>Credential handling</h3>
          <p>Tokens are kept in <code>sessionStorage</code>, removed when you disconnect, and omitted from URLs and telemetry.</p>
          <p>For a multi-user production deployment, replace static API tokens with an OIDC provider and a backend-for-frontend session using secure, HTTP-only cookies.</p>
          <p>Keep the runner token outside this UI. The console never needs permission to lease or complete execution jobs.</p>
        </aside>
      </div>
    </>
  );
}
