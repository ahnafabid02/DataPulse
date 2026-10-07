import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  ArrowRight,
  CheckCircle2,
  Hospital,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import {
  allPages,
  api,
  ApiError,
  type AuditEvent,
  type Credential,
  type Identity,
  type Organization,
  type Saved,
  type Source,
} from "./admin-api";

export function useIdentity() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    setChecking(true);
    setError("");
    try {
      setIdentity(await api<Identity>("/auth/me"));
    } catch (error) {
      setIdentity(null);
      if (error instanceof ApiError && error.status !== 401)
        setError(error.message);
    } finally {
      setChecking(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  return { identity, setIdentity, checking, error, refresh };
}
export type Access = ReturnType<typeof useIdentity>;

const activityNames: Record<string, string> = {
  "organization.created": "Hospital registered",
  "organization.updated": "Hospital details updated",
  "organization.retired": "Hospital registration retired",
  "source.created": "Record system registered",
  "source.updated": "Record system details or access updated",
  "source.retired": "Record system retired",
  "connector.credential_issued": "Connector access key issued",
  "connector.credential_rotated": "Connector access key replaced",
  "connector.credential_revoked": "Connector access key revoked",
  "auth.login": "Administrator signed in",
  "auth.logout": "Administrator signed out",
  "auth.login_failed": "Sign-in attempt rejected",
  "admin.created": "Administrator account created",
  "admin.password_changed": "Administrator password changed",
  "admin.password_reset": "Administrator password recovered locally",
  "audit.read": "Activity record viewed",
  "security.request_denied": "Request denied",
  "security.request_failed": "Request could not be completed",
};

function Message({ children }: { children: ReactNode }) {
  return (
    <p className="admin-error" role="alert">
      {children}
    </p>
  );
}
function Modal({
  title,
  children,
  onClose,
  busy = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement;
    ref.current?.showModal();
    return () => {
      if (previous instanceof HTMLElement && previous.isConnected)
        previous.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="wizard-dialog admin-dialog"
      aria-labelledby="admin-dialog-title"
      onCancel={(event) => {
        if (busy) event.preventDefault();
        else onClose();
      }}
    >
      <button
        className="dialog-close icon-button"
        aria-label="Close dialog"
        onClick={onClose}
        disabled={busy}
      >
        <X size={20} />
      </button>
      <h2 id="admin-dialog-title">{title}</h2>
      {children}
    </dialog>
  );
}
function SignIn({ access }: { access: Access }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <section className="panel admin-signin">
      <span className="task-icon green">
        <ShieldCheck size={24} />
      </span>
      <h2>Sign in to save hospital setup.</h2>
      <p>
        The administrator can add fictional hospitals, manage their access, and
        view the activity record. Saved registrations stay after you close
        DataPulse.
      </p>
      {(error || access.error) && <Message>{error || access.error}</Message>}
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setError("");
          try {
            access.setIdentity(
              await api<Identity>("/auth/login", "POST", {
                username,
                password,
              }),
            );
            setPassword("");
          } catch (error) {
            setError((error as Error).message);
            setPassword("");
          } finally {
            setBusy(false);
          }
        }}
      >
        <label className="form-label">
          Administrator username
          <input
            required
            autoComplete="username"
            maxLength={100}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </label>
        <label className="form-label">
          Password
          <input
            required
            type="password"
            autoComplete="current-password"
            maxLength={128}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <button className="button primary" disabled={busy || access.checking}>
          {busy
            ? "Signing in…"
            : access.checking
              ? "Checking sign-in…"
              : "Sign in"}
          <ArrowRight size={16} />
        </button>
      </form>
      <details className="admin-help">
        <summary>First time signing in?</summary>
        <p>
          A technical colleague creates the administrator account on this
          computer. There is no default password or public account registration.
          See the local setup guide in the project README.
        </p>
      </details>
      <p className="muted">
        You can still explore the clearly marked field review and patient
        matching previews from the menu.
      </p>
    </section>
  );
}

export default function AdminHospitals({
  access,
  onCount,
}: {
  access: Access;
  onCount: (value: number | null) => void;
}) {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [wizard, setWizard] = useState(false);
  const [credential, setCredential] = useState<Credential | null>(null);
  const [manage, setManage] = useState<Source | null>(null);
  const [auditOpen, setAuditOpen] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const administrator =
    access.identity?.roles.includes("platform_admin") &&
    access.identity.kind === "human";
  const report = (error: unknown) => {
    setError((error as Error).message);
    if (error instanceof ApiError && error.status === 401) {
      access.setIdentity(null);
      setCredential(null);
      setWizard(false);
      setManage(null);
      onCount(null);
    }
  };
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [orgs, systems] = await Promise.all([
        allPages<Organization>("/organizations"),
        allPages<Source>("/sources"),
      ]);
      setOrganizations(orgs);
      setSources(systems);
      onCount(orgs.length);
    } catch (error) {
      setError((error as Error).message);
      if (error instanceof ApiError && error.status === 401)
        access.setIdentity(null);
    } finally {
      setLoading(false);
    }
  }, [onCount, access.setIdentity]);
  useEffect(() => {
    if (administrator) void load();
    else {
      setSources([]);
      setOrganizations([]);
      setCredential(null);
      setWizard(false);
      setManage(null);
      setAuditOpen(false);
      setPasswordOpen(false);
      onCount(null);
    }
  }, [administrator, load, onCount]);
  const visible = organizations.filter((org) =>
    `${org.name} ${org.code} ${sources
      .filter((s) => s.organization_id === org.id)
      .map((s) => s.ehr_product)
      .join(" ")}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">SAVED HOSPITAL SETUP · LOCAL DEMO</div>
          <h1>Your hospitals, in one place.</h1>
          <p>
            Register fictional hospitals and their record systems. No hospital
            database is connected at this stage.
          </p>
        </div>
        {administrator && (
          <button
            className="button primary"
            onClick={() => setWizard(true)}
            disabled={loading}
          >
            <Plus size={17} />
            Add hospital or record system
          </button>
        )}
      </div>
      {!access.identity ? (
        <SignIn access={access} />
      ) : !administrator ? (
        <Message>
          This account cannot manage hospital setup. Use the platform
          administrator account.
        </Message>
      ) : (
        <>
          <div className="callout">
            <ShieldCheck size={20} />
            <p>
              <strong>Saved, but not connected.</strong> These registrations are
              stored in DataPulse. Adding one does not open a hospital database
              or transfer patient information.
            </p>
          </div>
          <div className="admin-toolbar">
            <span>
              Signed in as <strong>{access.identity.username}</strong>
            </span>
            <div>
              <button
                className="button secondary"
                onClick={() => void load()}
                disabled={loading}
              >
                <RefreshCw size={16} />
                Refresh registrations
              </button>
              <button
                className="button secondary"
                onClick={() => setAuditOpen(true)}
              >
                Activity record
              </button>
              <button
                className="button secondary"
                onClick={() => setPasswordOpen(true)}
              >
                Change password
              </button>
            </div>
          </div>
          {error && <Message>{error}</Message>}
          {notice && (
            <p className="admin-notice" role="status">
              {notice}
            </p>
          )}
          <div className="section-heading">
            <h2>
              Saved hospitals{" "}
              <span className="muted-count">{organizations.length}</span>
            </h2>
            <label className="search">
              <Search size={17} />
              <input
                aria-label="Search hospitals"
                placeholder="Find a hospital…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
          </div>
          {loading && <p role="status">Loading saved registrations…</p>}
          {!loading && !organizations.length && !error && (
            <div className="empty">
              <Hospital size={32} />
              <h3>Start with your first demo hospital.</h3>
              <p>
                Add a fictional hospital and one of its record systems. You can
                add more systems to the same hospital later.
              </p>
              <button
                className="button primary"
                onClick={() => setWizard(true)}
              >
                Add your first hospital
              </button>
            </div>
          )}
          <div className="hospital-grid">
            {visible.map((org) => (
              <article className="panel hospital-card" key={org.id}>
                <div className="hospital-card-top">
                  <span className="hospital-monogram">
                    <Hospital size={25} />
                  </span>
                  <span className="badge green">Registration saved</span>
                </div>
                <h2>{org.name}</h2>
                <p className="muted">Hospital code: {org.code}</p>
                {sources
                  .filter((s) => s.organization_id === org.id)
                  .map((source) => (
                    <section className="admin-source" key={source.id}>
                      <strong>{source.ehr_product}</strong>
                      <span
                        className={`badge ${source.status === "suspended" ? "amber" : "neutral"}`}
                      >
                        {source.status === "suspended"
                          ? "Access paused"
                          : "Saved · not connected"}
                      </span>
                      <p>Record system code: {source.code}</p>
                      <button
                        className="button secondary full"
                        onClick={() => setManage(source)}
                      >
                        Manage this record system
                        <ArrowRight size={16} />
                      </button>
                    </section>
                  ))}
                <button
                  className="button secondary full"
                  onClick={() => setWizard(true)}
                >
                  Add another record system
                  <Plus size={16} />
                </button>
              </article>
            ))}
          </div>
          {!loading && organizations.length > 0 && !visible.length && (
            <p>No matching hospitals. Try another name or record system.</p>
          )}
        </>
      )}
      {wizard && (
        <SetupWizard
          organizations={organizations}
          onClose={() => setWizard(false)}
          onSaved={(saved) => {
            setWizard(false);
            setCredential(saved.credential);
            setNotice(
              `${saved.organization.name} and its record system are saved. No database connection was made.`,
            );
            void load();
          }}
          onExpired={() => access.setIdentity(null)}
        />
      )}
      {credential && (
        <CredentialDialog
          credential={credential}
          onClose={() => setCredential(null)}
        />
      )}
      {manage && (
        <ManageSource
          source={manage}
          onClose={() => setManage(null)}
          onSaved={() => {
            setManage(null);
            setNotice(
              "Registration updated. The activity record includes this change.",
            );
            void load();
          }}
          onCredential={(value) => {
            setManage(null);
            setCredential(value);
          }}
          onError={report}
        />
      )}
      {auditOpen && <AuditDialog onClose={() => setAuditOpen(false)} />}
      {passwordOpen && (
        <PasswordDialog
          onClose={() => setPasswordOpen(false)}
          onChanged={() => {
            setPasswordOpen(false);
            access.setIdentity(null);
            onCount(null);
          }}
        />
      )}
    </>
  );
}

function SetupWizard({
  organizations,
  onClose,
  onSaved,
  onExpired,
}: {
  organizations: Organization[];
  onClose: () => void;
  onSaved: (saved: Saved) => void;
  onExpired: () => void;
}) {
  const [step, setStep] = useState(1);
  const [existing, setExisting] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [sourceCode, setSourceCode] = useState("primary");
  const [product, setProduct] = useState("OpenMRS");
  const [version, setVersion] = useState("");
  const [vendor, setVendor] = useState("mysql");
  const [databaseName, setDatabaseName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selectedName = existing
    ? organizations.find((org) => org.id === existing)?.name
    : name;
  return (
    <Modal
      title={
        step === 1
          ? "Tell us about your demo hospital."
          : "Check the registration before saving."
      }
      onClose={onClose}
      busy={busy}
    >
      <div className="eyebrow">STEP {step} OF 2 · FICTIONAL DETAILS ONLY</div>
      <p>
        {step === 1
          ? "We’ll save a hospital and its record system. You won’t need a database password or address."
          : "This saves setup details in DataPulse and creates a separate access key for this record system."}
      </p>
      {error && <Message>{error}</Message>}
      {step === 1 ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setStep(2);
          }}
        >
          {organizations.length > 0 && (
            <label className="form-label">
              Which hospital?
              <select
                value={existing}
                onChange={(e) => setExisting(e.target.value)}
              >
                <option value="">Add a new hospital</option>
                {organizations.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {!existing && (
            <>
              <label className="form-label">
                Hospital name
                <input
                  required
                  maxLength={255}
                  placeholder="For example, Demo Community Hospital"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
                <small>Use a fictional hospital for this local demo.</small>
              </label>
              <label className="form-label">
                Hospital code
                <input
                  required
                  maxLength={100}
                  pattern="[a-zA-Z0-9][a-zA-Z0-9_-]*"
                  placeholder="For example, demo-community"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
                <small>
                  A short, unique label. Use letters, numbers, hyphens or
                  underscores. It stays the same after registration.
                </small>
              </label>
            </>
          )}
          <label className="form-label">
            Record system name
            <input
              required
              maxLength={100}
              value={product}
              onChange={(e) => setProduct(e.target.value)}
            />
            <small>
              For example, OpenMRS, OpenEMR, or your fictional system’s name.
            </small>
          </label>
          <label className="form-label">
            Record system code
            <input
              required
              maxLength={100}
              pattern="[a-zA-Z0-9][a-zA-Z0-9_-]*"
              value={sourceCode}
              onChange={(e) => setSourceCode(e.target.value)}
            />
            <small>
              Unique within this hospital. For example, primary or outpatient.
            </small>
          </label>
          <label className="form-label">
            System version (optional)
            <input
              maxLength={100}
              value={version}
              onChange={(e) => setVersion(e.target.value)}
            />
          </label>
          <details className="admin-help" open>
            <summary>Details a technical colleague can help with</summary>
            <p>
              These are labels only. DataPulse won’t connect to this database.
            </p>
            <label className="form-label">
              Database type
              <select
                value={vendor}
                onChange={(e) => setVendor(e.target.value)}
              >
                <option value="mysql">MySQL</option>
                <option value="mariadb">MariaDB</option>
                <option value="postgresql">PostgreSQL</option>
                <option value="sqlserver">SQL Server</option>
                <option value="oracle">Oracle</option>
              </select>
            </label>
            <label className="form-label">
              Demo database name
              <input
                required
                maxLength={255}
                pattern="[a-zA-Z0-9][a-zA-Z0-9_.-]*"
                placeholder="For example, fictional_hospital"
                value={databaseName}
                onChange={(e) => setDatabaseName(e.target.value)}
              />
              <small>
                Use a demo name with letters, numbers, dots, hyphens or
                underscores. Do not enter an address or password.
              </small>
            </label>
          </details>
          <div className="dialog-actions">
            <button
              type="button"
              className="button secondary"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              className="button primary"
              disabled={
                (!existing && (!name.trim() || !code.trim())) ||
                !product.trim() ||
                !sourceCode.trim() ||
                !databaseName.trim()
              }
            >
              Continue
              <ArrowRight size={16} />
            </button>
          </div>
        </form>
      ) : (
        <>
          <dl className="confirmation-details">
            <div>
              <dt>Hospital</dt>
              <dd>{selectedName}</dd>
            </div>
            <div>
              <dt>Record system</dt>
              <dd>
                {product} · {sourceCode}
              </dd>
            </div>
            <div>
              <dt>Database label</dt>
              <dd>
                {databaseName} ({vendor})
              </dd>
            </div>
            <div>
              <dt>Next step</dt>
              <dd>
                Save the access key for your technical colleague. Database
                connection comes in a later milestone.
              </dd>
            </div>
          </dl>
          <div className="callout">
            <ShieldCheck size={18} />
            <p>
              No patient data is transferred. Your setup survives reload and
              restart.
            </p>
          </div>
          <div className="dialog-actions">
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => setStep(1)}
            >
              Go back
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  onSaved(
                    await api<Saved>("/onboarding", "POST", {
                      ...(existing
                        ? { organization_id: existing }
                        : { organization: { name, code } }),
                      source: {
                        code: sourceCode,
                        ehr_product: product,
                        ehr_version: version.trim() || null,
                        database_vendor: vendor,
                        database_name: databaseName,
                      },
                    }),
                  );
                } catch (error) {
                  setError((error as Error).message);
                  if (error instanceof ApiError && error.status === 401)
                    onExpired();
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? "Saving registration…" : "Save hospital setup"}
              <CheckCircle2 size={16} />
            </button>
          </div>
        </>
      )}
    </Modal>
  );
}

function CredentialDialog({
  credential,
  onClose,
}: {
  credential: Credential;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [error, setError] = useState("");
  return (
    <Modal title="Keep this record system’s access key safe." onClose={onClose}>
      <p>
        This key lets its connector read only its own registration. Give it to
        the technical colleague setting up this fictional source. It is
        different from a hospital database password.
      </p>
      <div className="callout">
        <ShieldCheck size={18} />
        <p>
          <strong>Shown once.</strong> DataPulse stores only a verification
          hash. After closing, you can replace this key but cannot retrieve it.
        </p>
      </div>
      <label className="form-label">
        Connector access key
        <textarea
          className="credential-value"
          readOnly
          value={credential.token}
          spellCheck={false}
        />
      </label>
      <p>
        Expires {new Date(credential.expires_at).toLocaleDateString("en-GB")}.
      </p>
      <button
        className="button secondary"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(credential.token);
            setCopied(true);
          } catch {
            setError(
              "Copy isn’t available here. Select the key and copy it manually.",
            );
          }
        }}
      >
        {copied ? "Copied" : "Copy access key"}
      </button>
      {error && <Message>{error}</Message>}
      <label className="admin-check">
        <input
          type="checkbox"
          checked={acknowledged}
          onChange={(e) => setAcknowledged(e.target.checked)}
        />
        I have saved it securely, or I’ll replace it when needed.
      </label>
      <button
        className="button primary"
        disabled={!acknowledged}
        onClick={onClose}
      >
        Done
      </button>
    </Modal>
  );
}

function ManageSource({
  source,
  onClose,
  onSaved,
  onCredential,
  onError,
}: {
  source: Source;
  onClose: () => void;
  onSaved: () => void;
  onCredential: (value: Credential) => void;
  onError: (error: unknown) => void;
}) {
  const [product, setProduct] = useState(source.ehr_product);
  const [version, setVersion] = useState(source.ehr_version || "");
  const [vendor, setVendor] = useState(source.database_vendor);
  const [name, setName] = useState(source.database_name);
  const [status, setStatus] = useState(source.status);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [retire, setRetire] = useState(false);
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (error) {
      setError((error as Error).message);
      onError(error);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title="Manage this record system." onClose={onClose} busy={busy}>
      <p>
        Changes are saved and recorded in the activity record. The source
        identity and hospital stay the same.
      </p>
      {error && <Message>{error}</Message>}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void run(async () => {
            await api(`/sources/${source.id}`, "PATCH", {
              expected_revision: source.revision,
              ehr_product: product,
              ehr_version: version.trim() || null,
              database_vendor: vendor,
              database_name: name,
              status,
            });
            onSaved();
          });
        }}
      >
        <label className="form-label">
          Record system name
          <input
            required
            maxLength={100}
            value={product}
            onChange={(e) => setProduct(e.target.value)}
          />
        </label>
        <label className="form-label">
          System version (optional)
          <input
            maxLength={100}
            value={version}
            onChange={(e) => setVersion(e.target.value)}
          />
        </label>
        <label className="form-label">
          Database type
          <select value={vendor} onChange={(e) => setVendor(e.target.value)}>
            {["mysql", "mariadb", "postgresql", "sqlserver", "oracle"].map(
              (value) => (
                <option key={value}>{value}</option>
              ),
            )}
          </select>
        </label>
        <label className="form-label">
          Demo database name
          <input
            required
            maxLength={255}
            pattern="[a-zA-Z0-9][a-zA-Z0-9_.-]*"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label className="form-label">
          Connector access
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="registered">Registration saved</option>
            <option value="suspended">Pause access</option>
          </select>
          <small>
            Pausing access revokes its keys. After resuming, issue a new key.
            Neither option connects a database.
          </small>
        </label>
        <button className="button primary" disabled={busy}>
          {busy ? "Working…" : "Save changes"}
        </button>
      </form>
      <section className="admin-security">
        <h3>Access key</h3>
        <p>
          Replacing a key immediately disables the old one. Revoking a key stops
          connector access until a replacement is issued.
        </p>
        <button
          className="button secondary"
          disabled={busy || source.status === "suspended"}
          onClick={() =>
            void run(async () => {
              onCredential(
                await api<Credential>(
                  `/sources/${source.id}/credential`,
                  "POST",
                ),
              );
            })
          }
        >
          Replace access key
        </button>
        <button
          className="button secondary"
          disabled={busy}
          onClick={() =>
            void run(async () => {
              await api(`/sources/${source.id}/credential`, "DELETE");
              onSaved();
            })
          }
        >
          Revoke access key
        </button>
      </section>
      <details className="admin-help">
        <summary>Retire this registration</summary>
        <p>
          This hides the registration and permanently stops its connector
          access. Its identity and activity history are kept.
        </p>
        <label className="admin-check">
          <input
            type="checkbox"
            checked={retire}
            onChange={(e) => setRetire(e.target.checked)}
          />
          I want to retire this demo source system.
        </label>
        <button
          className="button secondary"
          disabled={busy || !retire}
          onClick={() =>
            void run(async () => {
              await api(
                `/sources/${source.id}?expected_revision=${source.revision}`,
                "DELETE",
              );
              onSaved();
            })
          }
        >
          Retire record system
        </button>
      </details>
    </Modal>
  );
}

function AuditDialog({ onClose }: { onClose: () => void }) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async (next?: string) => {
    setBusy(true);
    setError("");
    try {
      const page = await api<{
        items: AuditEvent[];
        next_cursor: string | null;
      }>(`/audit-events?limit=50${next ? `&cursor=${next}` : ""}`);
      setEvents((previous) =>
        next ? [...previous, ...page.items] : page.items,
      );
      setCursor(page.next_cursor);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <Modal title="Activity record" onClose={onClose}>
      <p>
        A permanent record of registration and security actions. Entries cannot
        be edited or removed through DataPulse.
      </p>
      {error && <Message>{error}</Message>}
      {busy && <p role="status">Loading activity…</p>}
      <div className="admin-audit">
        {events.map((event) => (
          <article key={event.id}>
            <strong>{activityNames[event.action] || event.action}</strong>
            <time dateTime={event.occurred_at}>
              {new Date(event.occurred_at).toLocaleString("en-GB")}
            </time>
            <p>
              Actor:{" "}
              {event.actor_kind === "human"
                ? "Administrator"
                : event.actor_kind === "operator"
                  ? "Local setup operator"
                  : event.actor_kind === "connector"
                    ? "Source connector"
                    : "Signed-out request"}
            </p>
            <details>
              <summary>Change details</summary>
              <p>Actor identity: {event.actor_id || event.actor_kind}</p>
              <p>
                Target: {event.target_type} · {event.target_id || "Request"}
              </p>
              <pre>{JSON.stringify(event.change_metadata, null, 2)}</pre>
            </details>
          </article>
        ))}
      </div>
      {cursor && (
        <button
          className="button secondary"
          disabled={busy}
          onClick={() => void load(cursor)}
        >
          Load more activity
        </button>
      )}
    </Modal>
  );
}
function PasswordDialog({
  onClose,
  onChanged,
}: {
  onClose: () => void;
  onChanged: () => void;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <Modal title="Change your password." onClose={onClose} busy={busy}>
      <p>
        Choose 12–128 characters. All administrator sessions will end, including
        this one. Sign in again with the new password.
      </p>
      {error && <Message>{error}</Message>}
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (next !== confirm) {
            setError("The new passwords do not match.");
            return;
          }
          setBusy(true);
          setError("");
          try {
            await api("/auth/password", "POST", {
              current_password: current,
              new_password: next,
            });
            setCurrent("");
            setNext("");
            setConfirm("");
            onChanged();
          } catch (error) {
            setError((error as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label className="form-label">
          Current password
          <input
            type="password"
            autoComplete="current-password"
            required
            maxLength={128}
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </label>
        <label className="form-label">
          New password
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
            maxLength={128}
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
        </label>
        <label className="form-label">
          Confirm new password
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
            maxLength={128}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </label>
        <button className="button primary" disabled={busy}>
          {busy ? "Updating password…" : "Change password and sign out"}
        </button>
      </form>
    </Modal>
  );
}
