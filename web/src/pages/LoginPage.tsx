import { ArrowRight, Boxes, CheckCircle2, KeyRound, LockKeyhole, Server } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { useAuth } from "../context/AuthContext";
import { api, setApiBase } from "../lib/api";

const credentialsSchema = z.object({
  apiUrl: z.string().refine((value) => !value || URL.canParse(value), "Enter a valid API URL or leave it blank for same-origin."),
  controlToken: z.string().min(8, "The developer token must contain at least 8 characters."),
  adminToken: z.string(),
  actor: z.string().min(2, "Enter the identity recorded in audit events.")
});

export function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [apiUrl, setApiUrl] = useState(auth.apiUrl);
  const [controlToken, setControlToken] = useState(auth.controlToken);
  const [adminToken, setAdminToken] = useState(auth.adminToken);
  const [actor, setActor] = useState(auth.actor);
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(false);

  async function connect(event: FormEvent) {
    event.preventDefault();
    const parsed = credentialsSchema.safeParse({ apiUrl, controlToken, adminToken, actor });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Check the connection details.");
      return;
    }
    setChecking(true);
    setError("");
    setApiBase(apiUrl);
    try {
      await api.summary(controlToken);
      auth.save({ apiUrl, controlToken, adminToken, actor });
      navigate("/overview", { replace: true });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not connect to the control plane.");
    } finally {
      setChecking(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-story">
        <div className="brand-row login-brand"><div className="brand-mark"><Boxes size={20} /></div><div><strong>VersionWeaver</strong><span>Migration reliability platform</span></div></div>
        <div className="story-copy">
          <p className="eyebrow">Safe change, visible end to end</p>
          <h1>One control room for every dependency and model migration.</h1>
          <p>Plan upgrades, approve risk, follow isolated execution, and retain evidence without giving the hosted control plane access to repository execution.</p>
        </div>
        <div className="login-flow" aria-label="Migration workflow">
          {['Discover', 'Approve', 'Execute', 'Verify'].map((item, index) => <div key={item}><span>0{index + 1}</span><strong>{item}</strong></div>)}
        </div>
        <div className="trust-note"><LockKeyhole size={18} /><span>Tokens remain in this browser tab and are never placed in URLs.</span></div>
      </section>
      <section className="login-panel">
        <form className="login-card" onSubmit={connect}>
          <div className="login-card-head"><div className="login-icon"><Server size={22} /></div><div><p className="eyebrow">Control plane</p><h2>Connect your console</h2></div></div>
          <p className="form-intro">Use a developer token for workflow access. Add an admin token to view the audit ledger.</p>
          <label>API URL<span>Leave blank when the UI and API share a host.</span><input value={apiUrl} onChange={(event) => setApiUrl(event.target.value)} placeholder="https://api.example.com" /></label>
          <label>Developer token<input type="password" autoComplete="new-password" value={controlToken} onChange={(event) => setControlToken(event.target.value)} placeholder="Required" /></label>
          <label>Admin token <em>optional</em><input type="password" autoComplete="new-password" value={adminToken} onChange={(event) => setAdminToken(event.target.value)} placeholder="Unlocks audit events" /></label>
          <label>Audit identity<input value={actor} onChange={(event) => setActor(event.target.value)} placeholder="you@example.com" /></label>
          {error && <div className="form-error" role="alert">{error}</div>}
          <button className="button button-primary button-wide" disabled={checking} type="submit"><KeyRound size={17} />{checking ? "Validating access…" : "Connect securely"}<ArrowRight size={17} /></button>
          <div className="form-foot"><CheckCircle2 size={15} /><span>Uses the API’s existing role-scoped authentication.</span></div>
        </form>
      </section>
    </main>
  );
}
