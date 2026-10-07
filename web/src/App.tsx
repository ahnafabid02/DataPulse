import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  FileCheck2,
  FlaskConical,
  HeartPulse,
  Hospital as HospitalIcon,
  Info,
  LayoutDashboard,
  Link2,
  ListFilter,
  MapPin,
  Menu,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Stethoscope,
  Users,
  X,
} from "lucide-react";
import {
  fields,
  hospitals as initialHospitals,
  timeline,
  type Hospital,
  type Page,
  type ReviewDecision,
} from "./data";

const navigation: { id: Page; label: string; icon: typeof Activity }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "hospitals", label: "Hospitals", icon: HospitalIcon },
  { id: "fields", label: "Field review", icon: FileCheck2 },
  { id: "identity", label: "Patient matching", icon: Users },
  { id: "patients", label: "Patient records", icon: HeartPulse },
];
const titles: Record<Page, string> = {
  overview: "Overview",
  hospitals: "Hospitals",
  fields: "Field review",
  identity: "Patient matching",
  patients: "Patient records",
  help: "Help & guidance",
};
function initialPage(): Page {
  return [...navigation.map((n) => n.id), "help"].includes(
    window.location.hash.slice(1),
  )
    ? (window.location.hash.slice(1) as Page)
    : "overview";
}
function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "green" | "amber";
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
function Empty({
  title,
  text,
  children,
}: {
  title: string;
  text: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <CheckCircle2 size={32} />
      <h3>{title}</h3>
      <p>{text}</p>
      {children}
    </div>
  );
}
function PageHeading({
  eyebrow,
  title,
  text,
  children,
}: {
  eyebrow: string;
  title: string;
  text: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{text}</p>
      </div>
      {children}
    </div>
  );
}

function useHealth() {
  const [state, setState] = useState<
    "checking" | "ready" | "attention" | "offline"
  >("checking");
  const [checked, setChecked] = useState<Date | null>(null);
  const active = useRef<AbortController | null>(null);
  const refresh = useCallback(async () => {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setState("checking");
    const timeout = window.setTimeout(() => controller.abort(), 5000);
    try {
      const [live, ready] = await Promise.all(
        ["/health/live", "/health/ready"].map(async (url) => {
          const response = await fetch(url, {
            signal: controller.signal,
            cache: "no-store",
          });
          const body: unknown = await response.json();
          const status =
            typeof body === "object" && body !== null && "status" in body
              ? body.status
              : null;
          return { ok: response.ok, status };
        }),
      );
      if (active.current !== controller) return;
      setState(
        live.ok && live.status === "ok"
          ? ready.ok && ready.status === "ready"
            ? "ready"
            : "attention"
          : "offline",
      );
      setChecked(new Date());
    } catch {
      if (active.current === controller) {
        setState("offline");
        setChecked(new Date());
      }
    } finally {
      window.clearTimeout(timeout);
    }
  }, []);
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 45000);
    return () => {
      window.clearInterval(timer);
      active.current?.abort();
      active.current = null;
    };
  }, [refresh]);
  return { state, checked, refresh };
}

export default function App() {
  const [page, setPage] = useState<Page>(initialPage);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [hospitals, setHospitals] = useState(initialHospitals);
  const [reviews, setReviews] = useState<Record<string, ReviewDecision>>({});
  const [identity, setIdentity] = useState<"pending" | "linked" | "separate">(
    "pending",
  );
  const [toast, setToast] = useState("");
  const [wizard, setWizard] = useState(false);
  const health = useHealth();
  const main = useRef<HTMLElement>(null);
  const navigationPanel = useRef<HTMLElement>(null);
  const menuClose = useRef<HTMLButtonElement>(null);
  const menuToggle = useRef<HTMLButtonElement>(null);
  const closeMenu = () => {
    setMobileMenu(false);
    window.requestAnimationFrame(() => menuToggle.current?.focus());
  };
  useEffect(() => {
    if (mobileMenu) menuClose.current?.focus();
  }, [mobileMenu]);
  const firstRender = useRef(true);
  const navigate = (next: Page) => {
    window.location.hash = next;
    setPage(next);
    setMobileMenu(false);
  };
  useEffect(() => {
    const change = () => setPage(initialPage());
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    main.current?.focus();
    window.scrollTo(0, 0);
  }, [page]);
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 6500);
    return () => window.clearTimeout(timer);
  }, [toast]);
  const pendingFields = fields.filter((field) => !reviews[field.id]).length;
  const reset = () => {
    setReviews({});
    setIdentity("pending");
    setHospitals(initialHospitals);
    setToast("The preview has been reset. You can explore it again.");
  };
  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#main-content"
        onClick={(e) => {
          e.preventDefault();
          main.current?.focus();
        }}
      >
        Skip to content
      </a>
      {mobileMenu && (
        <button
          className="menu-scrim"
          aria-label="Close navigation"
          onClick={closeMenu}
        />
      )}
      <aside
        id="workspace-navigation"
        ref={navigationPanel}
        className={`sidebar ${mobileMenu ? "mobile-open" : ""}`}
        onKeyDown={(event) => {
          if (event.key === "Escape") closeMenu();
          if (mobileMenu && event.key === "Tab") {
            const targets =
              navigationPanel.current?.querySelectorAll<HTMLElement>(
                "a[href], button:not([disabled])",
              );
            if (!targets?.length) return;
            const first = targets[0];
            const last = targets[targets.length - 1];
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first.focus();
            }
          }
        }}
      >
        <button
          className="icon-button mobile-nav-close"
          ref={menuClose}
          aria-label="Close navigation menu"
          onClick={closeMenu}
        >
          <X size={20} />
        </button>
        <a
          className="brand"
          href="#overview"
          onClick={() => navigate("overview")}
        >
          <span className="brand-mark">
            <Activity size={23} />
          </span>
          <span>
            DataPulse<small>CONNECTED CARE</small>
          </span>
        </a>
        <div className="workspace-label">YOUR WORKSPACE</div>
        <nav aria-label="Main navigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              aria-current={page === id ? "page" : undefined}
              className={`nav-item ${page === id ? "active" : ""}`}
              onClick={() => navigate(id)}
            >
              <Icon size={19} />
              <span>{label}</span>
              {id === "fields" && pendingFields > 0 && (
                <span className="nav-count">{pendingFields}</span>
              )}
              {id === "identity" && identity === "pending" && (
                <span className="nav-count">1</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-guide">
          <div className="guide-icon">
            <BookOpen size={20} />
          </div>
          <h3>A little guidance?</h3>
          <p>Understand each step of connecting care.</p>
          <button onClick={() => navigate("help")}>
            Open the guide <ArrowUpRight size={16} />
          </button>
        </div>
        <div className="sidebar-bottom">
          <span className="avatar small">DP</span>
          <div>
            <strong>Preview workspace</strong>
            <small>Explore at your own pace</small>
          </div>
          <ChevronDown size={15} />
        </div>
      </aside>
      <div className="workspace" inert={mobileMenu}>
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-toggle"
              ref={menuToggle}
              aria-label="Open navigation"
              aria-controls="workspace-navigation"
              aria-expanded={mobileMenu}
              onClick={() => setMobileMenu(true)}
            >
              <Menu size={22} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>{titles[page]}</strong>
          </div>
          <div className="topbar-right">
            <span className={`system-pill ${health.state}`}>
              <span className="status-dot" />
              {health.state === "checking"
                ? "Checking system"
                : health.state === "ready"
                  ? "System online"
                  : health.state === "attention"
                    ? "System needs attention"
                    : "System unavailable"}
            </span>
            <button
              className="help-top"
              aria-label="Help and guidance"
              onClick={() => navigate("help")}
            >
              <CircleHelp size={18} />
              <span>Help</span>
            </button>
            <span className="avatar tiny">DP</span>
          </div>
        </header>
        <div className="preview-banner">
          <div>
            <Sparkles size={16} />
            <strong>Guided preview</strong>
            <span className="banner-divider" />
            <span>Sample records only. Your actions stay in this session.</span>
          </div>
          <button onClick={reset}>
            <RefreshCw size={13} />
            Reset preview
          </button>
        </div>
        <main id="main-content" tabIndex={-1} ref={main}>
          {page === "overview" && (
            <Overview
              navigate={navigate}
              health={health}
              hospitalCount={hospitals.length}
              pendingFields={pendingFields}
              identityPending={identity === "pending"}
            />
          )}
          {page === "hospitals" && (
            <Hospitals
              hospitals={hospitals}
              navigate={navigate}
              openWizard={() => setWizard(true)}
            />
          )}
          {page === "fields" && (
            <FieldReview
              reviews={reviews}
              onDecision={(id, decision) => {
                setReviews((previous) => ({ ...previous, [id]: decision }));
                setToast(
                  decision === "approved"
                    ? "Example approved. Real hospital records have not changed."
                    : "Example sent back for correction. Real hospital records have not changed.",
                );
              }}
            />
          )}
          {page === "identity" && (
            <IdentityReview
              identity={identity}
              onDecision={(value) => {
                setIdentity(value);
                setToast(
                  value === "linked"
                    ? "Sample identities linked. Explore the combined preview in Patient records."
                    : "Sample identities kept separate. Neither hospital record was overwritten.",
                );
              }}
              navigate={navigate}
            />
          )}
          {page === "patients" && (
            <PatientRecords
              linked={identity === "linked"}
              navigate={navigate}
            />
          )}
          {page === "help" && <Help navigate={navigate} />}
          <footer className="footer">
            <span>
              <ShieldCheck size={14} /> Every record keeps its hospital of
              origin.
            </span>
            <span>DataPulse · Connected care, made clear</span>
          </footer>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={21} />
          <span>{toast}</span>
          <button aria-label="Dismiss message" onClick={() => setToast("")}>
            <X size={17} />
          </button>
        </div>
      )}
      {wizard && (
        <HospitalWizard
          onClose={() => setWizard(false)}
          onAdd={(hospital) => {
            setHospitals((previous) => [...previous, hospital]);
            setWizard(false);
            setToast(
              "Example hospital added for this session. No real connection has been made.",
            );
          }}
        />
      )}
    </div>
  );
}

function Overview({
  navigate,
  health,
  hospitalCount,
  pendingFields,
  identityPending,
}: {
  navigate: (page: Page) => void;
  health: ReturnType<typeof useHealth>;
  hospitalCount: number;
  pendingFields: number;
  identityPending: boolean;
}) {
  return (
    <>
      <PageHeading
        eyebrow="A CLEARER PICTURE OF CARE"
        title="Welcome to your care workspace."
        text="Connect hospitals. Review with confidence. See the whole patient journey."
      >
        <span className="heading-tag">
          <span className="status-dot" /> Guided introduction
        </span>
      </PageHeading>
      <section className="welcome-panel">
        <div className="welcome-copy">
          <div className="eyebrow">BETTER TOGETHER</div>
          <h2>
            Different hospitals.
            <br />
            One connected story.
          </h2>
          <p>
            DataPulse brings hospital records together while keeping where each
            record came from. You stay in control of what is approved.
          </p>
          <button
            className="button light"
            onClick={() => navigate("hospitals")}
          >
            Explore your hospitals <ArrowRight size={17} />
          </button>
          <span className="welcome-caption">
            Start with the sample workspace below.
          </span>
        </div>
        <CareIllustration />
      </section>
      <section className="journey-section" aria-labelledby="journey-title">
        <div className="section-heading">
          <div>
            <h2 id="journey-title">A simple path to connected care</h2>
            <p>
              Four steps. A person stays in control at every important decision.
            </p>
          </div>
          <button className="text-button" onClick={() => navigate("help")}>
            How it works <ArrowUpRight size={16} />
          </button>
        </div>
        <div className="journey">
          {[
            {
              title: "Add a hospital",
              text: "Tell us which hospital records to connect.",
              icon: HospitalIcon,
              page: "hospitals" as Page,
            },
            {
              title: "Check the meaning",
              text: "Review how information is understood.",
              icon: ClipboardCheck,
              page: "fields" as Page,
            },
            {
              title: "Confirm the person",
              text: "Check patient matches before linking.",
              icon: Users,
              page: "identity" as Page,
            },
            {
              title: "See the care journey",
              text: "Read a history with the source attached.",
              icon: HeartPulse,
              page: "patients" as Page,
            },
          ].map((step, i) => (
            <button
              className="journey-step"
              key={step.title}
              onClick={() => navigate(step.page)}
            >
              <div className="journey-top">
                <span className="step-icon">
                  <step.icon size={21} />
                </span>
                <span className="step-number">0{i + 1}</span>
              </div>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
              <span className="step-link">
                Explore step <ArrowRight size={15} />
              </span>
            </button>
          ))}
        </div>
      </section>
      <div className="overview-bottom">
        <section className="panel review-panel">
          <div className="section-heading">
            <div>
              <h2>Ready for a closer look</h2>
              <p>A few examples to help you get familiar.</p>
            </div>
            <Badge>Sample tasks</Badge>
          </div>
          <button className="task-row" onClick={() => navigate("fields")}>
            <span className="task-icon amber">
              <FileCheck2 size={21} />
            </span>
            <span>
              <strong>
                {pendingFields
                  ? `${pendingFields} field ${pendingFields === 1 ? "suggestion needs" : "suggestions need"} your review`
                  : "Field examples reviewed"}
              </strong>
              <small>
                Check names, dates, and the meaning of hospital codes.
              </small>
            </span>
            <ChevronRight size={19} />
          </button>
          <button className="task-row" onClick={() => navigate("identity")}>
            <span className="task-icon lavender">
              <Users size={21} />
            </span>
            <span>
              <strong>
                {identityPending
                  ? "One possible patient match to check"
                  : "Patient match example reviewed"}
              </strong>
              <small>Compare two records before deciding to link them.</small>
            </span>
            <ChevronRight size={19} />
          </button>
          <div className="review-footnote">
            <ShieldCheck size={16} /> Suggestions are reviewed by people before
            they are used.
          </div>
        </section>
        <section className="panel status-panel">
          <div className="section-heading">
            <h2>Live system status</h2>
            <button
              className="icon-button"
              aria-label="Refresh system status"
              onClick={() => void health.refresh()}
              disabled={health.state === "checking"}
            >
              <RefreshCw
                size={17}
                className={health.state === "checking" ? "spin" : ""}
              />
            </button>
          </div>
          <div className={`status-display ${health.state}`}>
            <span className="status-orbit">
              <Activity size={25} />
            </span>
            <div>
              <strong>
                {health.state === "ready"
                  ? "Ready when you are"
                  : health.state === "checking"
                    ? "Checking your workspace"
                    : health.state === "attention"
                      ? "Some services need attention"
                      : "We can’t reach the system"}
              </strong>
              <p>
                {health.state === "ready"
                  ? "The application and record store are responding."
                  : health.state === "checking"
                    ? "This usually takes just a moment."
                    : "You can still explore the sample workspace. Try refreshing the check."}
              </p>
            </div>
          </div>
          <div className="status-summary">
            <span>Sample hospitals</span>
            <strong>{hospitalCount}</strong>
          </div>
          <div className="status-summary">
            <span>Real hospital connections</span>
            <strong>Not set up yet</strong>
          </div>
          <small className="checked-at">
            {health.checked
              ? `Last checked at ${health.checked.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`
              : "Waiting for the first check"}{" "}
            · Updates automatically
          </small>
        </section>
      </div>
    </>
  );
}

function CareIllustration() {
  return (
    <div className="care-illustration" aria-hidden="true">
      <div className="orbit orbit-one" />
      <div className="orbit orbit-two" />
      <div className="illustration-label">
        <span className="status-dot" /> CONNECTED, WITH CONTEXT
      </div>
      <div className="hospital-node node-one">
        <span>
          <HospitalIcon size={20} />
        </span>
        <div>
          <strong>Meghna General</strong>
          <small>Hospital records</small>
        </div>
        <CheckCircle2 size={16} />
      </div>
      <div className="hospital-node node-two">
        <span>
          <HospitalIcon size={20} />
        </span>
        <div>
          <strong>Padma Care</strong>
          <small>Hospital records</small>
        </div>
        <CheckCircle2 size={16} />
      </div>
      <div className="connector-line line-one" />
      <div className="connector-line line-two" />
      <div className="story-node">
        <span className="story-icon">
          <HeartPulse size={29} />
        </span>
        <div>
          <small>THE BIGGER PICTURE</small>
          <strong>A patient’s care journey</strong>
          <span>Every source stays visible</span>
        </div>
        <div className="story-mini-line">
          <span />
          <span />
          <span />
        </div>
      </div>
      <span className="illustration-bottom">
        <ShieldCheck size={14} /> Original records are preserved
      </span>
    </div>
  );
}

function Hospitals({
  hospitals,
  navigate,
  openWizard,
}: {
  hospitals: Hospital[];
  navigate: (page: Page) => void;
  openWizard: () => void;
}) {
  const [query, setQuery] = useState("");
  const visible = hospitals.filter((h) =>
    `${h.name} ${h.location} ${h.system}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    <>
      <PageHeading
        eyebrow="CONNECT THE SOURCES OF CARE"
        title="Your hospitals, in one place."
        text="Each hospital keeps its own records. DataPulse helps them speak the same language."
      >
        <button className="button primary" onClick={openWizard}>
          <Plus size={18} />
          Add example hospital
        </button>
      </PageHeading>
      <div className="callout">
        <Info size={19} />
        <div>
          <strong>A safe place to explore</strong>
          <p>
            These hospitals are fictional examples. Real hospital setup will be
            available after secure access is ready. Don’t enter passwords or
            patient information.
          </p>
        </div>
      </div>
      <div className="section-heading">
        <h2>
          Sample hospitals{" "}
          <span className="muted-count">{hospitals.length}</span>
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
      <div className="hospital-grid">
        {visible.map((h, index) => (
          <article className="panel hospital-card" key={h.id}>
            <div className="hospital-card-top">
              <span
                className={`hospital-monogram ${index % 2 ? "purple" : ""}`}
              >
                <HospitalIcon size={25} />
              </span>
              <Badge tone={h.stage === "Ready for review" ? "green" : "amber"}>
                {h.stage}
              </Badge>
            </div>
            <h2>{h.name}</h2>
            <p className="location">
              <MapPin size={14} />
              {h.location} · Sample hospital
            </p>
            <dl className="hospital-details">
              <div>
                <dt>Hospital record system</dt>
                <dd>{h.system}</dd>
              </div>
              <div>
                <dt>Information stays with</dt>
                <dd>This hospital</dd>
              </div>
            </dl>
            <div className="mini-steps">
              <span className="done">
                <Check size={12} />
                Added
              </span>
              <span className={h.stage === "Ready for review" ? "done" : ""}>
                <Check size={12} />
                Understood
              </span>
              <span>Review</span>
            </div>
            <button
              className="button secondary full"
              onClick={() =>
                navigate(h.stage === "Ready for review" ? "fields" : "help")
              }
            >
              {h.stage === "Ready for review"
                ? "Review sample fields"
                : "See the next steps"}
              <ArrowRight size={16} />
            </button>
          </article>
        ))}
      </div>
      {!visible.length && (
        <Empty
          title="No matching hospitals"
          text="Try a hospital name, city, or record system."
        />
      )}
      <div className="bottom-note">
        <ShieldCheck size={18} />
        <span>
          <strong>One hospital at a time.</strong> Each connection is reviewed
          separately, even when hospitals use the same record system.
        </span>
      </div>
    </>
  );
}

function HospitalWizard({
  onClose,
  onAdd,
}: {
  onClose: () => void;
  onAdd: (hospital: Hospital) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [city, setCity] = useState("");
  const [system, setSystem] = useState("OpenMRS");
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  return (
    <dialog
      ref={dialog}
      className="wizard-dialog"
      aria-labelledby="wizard-title"
      onCancel={onClose}
    >
      <button
        className="dialog-close icon-button"
        onClick={onClose}
        aria-label="Close hospital setup"
      >
        <X size={20} />
      </button>
      <span className="task-icon green">
        <HospitalIcon size={25} />
      </span>
      <div className="eyebrow">STEP {step} OF 2 · PREVIEW ONLY</div>
      <h2 id="wizard-title">
        {step === 1
          ? "Tell us about your example hospital."
          : "A quick check before you continue."}
      </h2>
      <p>
        {step === 1
          ? "Use fictional details to try the setup experience. You won’t need any technical information."
          : "This adds a hospital to this preview session. It does not connect to a real hospital."}
      </p>
      <div className="wizard-progress">
        <span />
        <span className={step === 2 ? "complete" : ""} />
      </div>
      {step === 1 ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim() && city.trim()) setStep(2);
          }}
        >
          <label className="form-label">
            Hospital name
            <input
              required
              maxLength={100}
              placeholder="For example, Demo Community Hospital"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <small>Use a fictional name for this preview.</small>
          </label>
          <label className="form-label">
            City
            <input
              required
              maxLength={80}
              placeholder="For example, Sylhet"
              value={city}
              onChange={(e) => setCity(e.target.value)}
            />
          </label>
          <label className="form-label">
            Which record system does it use?
            <select value={system} onChange={(e) => setSystem(e.target.value)}>
              <option>OpenMRS</option>
              <option>OpenEMR</option>
              <option>Another system</option>
              <option>I’m not sure</option>
            </select>
            <small>
              It’s okay if you don’t know. A technical colleague can help later.
            </small>
          </label>
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
              disabled={!name.trim() || !city.trim()}
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
              <dt>Hospital name</dt>
              <dd>{name.trim()}</dd>
            </div>
            <div>
              <dt>City</dt>
              <dd>{city.trim()}</dd>
            </div>
            <div>
              <dt>Record system</dt>
              <dd>{system}</dd>
            </div>
          </dl>
          <div className="callout">
            <Info size={18} />
            <p>No real connection or data transfer will take place.</p>
          </div>
          <div className="dialog-actions">
            <button className="button secondary" onClick={() => setStep(1)}>
              Go back
            </button>
            <button
              className="button primary"
              onClick={() =>
                onAdd({
                  id: crypto.randomUUID(),
                  name: name.trim(),
                  location: city.trim(),
                  system,
                  stage: "Setup draft",
                })
              }
            >
              Add to preview
              <Check size={16} />
            </button>
          </div>
        </>
      )}
    </dialog>
  );
}

function FieldReview({
  reviews,
  onDecision,
}: {
  reviews: Record<string, ReviewDecision>;
  onDecision: (id: string, decision: ReviewDecision) => void;
}) {
  const [selected, setSelected] = useState("gender");
  const [filter, setFilter] = useState("pending");
  const visible = fields.filter((f) => filter === "all" || !reviews[f.id]);
  const field = fields.find((f) => f.id === selected)!;
  return (
    <>
      <PageHeading
        eyebrow="MAKE INFORMATION MEAN THE SAME THING"
        title="A human check makes the difference."
        text="Review how a hospital’s information will appear in a shared patient record."
      />
      <div className="callout">
        <CircleHelp size={20} />
        <div>
          <strong>What am I reviewing?</strong>
          <p>
            A hospital might write “F” for a patient’s gender. You check that
            DataPulse understands it as “Female” before that suggestion is used.
          </p>
        </div>
      </div>
      <div className="review-layout">
        <section className="panel review-list">
          <div className="section-heading">
            <h2>Field suggestions</h2>
            <label>
              <span className="sr-only">Filter suggestions</span>
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              >
                <option value="pending">To review</option>
                <option value="all">All examples</option>
              </select>
            </label>
          </div>
          {visible.map((f) => (
            <button
              className={`review-list-item ${selected === f.id ? "selected" : ""}`}
              key={f.id}
              onClick={() => setSelected(f.id)}
            >
              <span className="field-row-title">
                {f.title}
                <ChevronRight size={15} />
              </span>
              <small>{f.hospital}</small>
              <Badge
                tone={
                  reviews[f.id]
                    ? reviews[f.id] === "approved"
                      ? "green"
                      : "neutral"
                    : f.id === "date"
                      ? "amber"
                      : "neutral"
                }
              >
                {reviews[f.id]
                  ? reviews[f.id] === "approved"
                    ? "Approved in preview"
                    : "Returned for correction"
                  : f.level}
              </Badge>
            </button>
          ))}
          {!visible.length && (
            <Empty
              title="All examples reviewed"
              text="You can revisit your choices using “All examples”."
            />
          )}
        </section>
        <section className="panel field-detail" aria-labelledby="field-title">
          <div className="section-heading">
            <span className="eyebrow">SAMPLE SUGGESTION</span>
            <Badge>{field.system}</Badge>
          </div>
          <h2 id="field-title">{field.title}</h2>
          <p>{field.meaning}</p>
          <div className="translation">
            <div>
              <small>THE HOSPITAL WRITES</small>
              <strong>{field.example}</strong>
              <span>Field: {field.source}</span>
            </div>
            <span className="translation-arrow">
              <ArrowRight size={22} />
            </span>
            <div>
              <small>THE SHARED RECORD SHOWS</small>
              <strong>{field.target}</strong>
              <span>
                {field.id === "date"
                  ? "Confirm the date format first"
                  : "A meaning other systems understand"}
              </span>
            </div>
          </div>
          <div className="evidence-block">
            <h3>
              <BookOpen size={17} />
              Why this was suggested
            </h3>
            <p>{field.reason}</p>
            <div className="value-chips">
              {field.alternatives.map((value) => (
                <span key={value}>{value}</span>
              ))}
            </div>
          </div>
          {field.id === "date" && (
            <div className="callout amber">
              <Info size={19} />
              <p>
                <strong>This needs clarification.</strong> We don’t guess when a
                date could have two meanings. Send it back so the format can be
                checked.
              </p>
            </div>
          )}
          <details className="technical-details">
            <summary>
              Details for a technical colleague <ChevronDown size={15} />
            </summary>
            <p>
              Source field: <code>{field.source}</code>
              <br />
              FHIR destination: <code>{field.technical}</code>
              <br />
              This is a sample proposal, not an active hospital mapping.
            </p>
          </details>
          <div className="decision-area">
            {reviews[field.id] ? (
              <div className="decision-complete">
                <CheckCircle2 size={20} />
                <span>
                  {reviews[field.id] === "approved"
                    ? "You approved this example."
                    : "You returned this example for correction."}
                </span>
                <button
                  className="text-button"
                  onClick={() => {
                    const next = fields.find((f) => !reviews[f.id]);
                    if (next) setSelected(next.id);
                    else setFilter("all");
                  }}
                >
                  {fields.some((f) => !reviews[f.id])
                    ? "Next suggestion"
                    : "See all examples"}
                  <ArrowRight size={15} />
                </button>
              </div>
            ) : (
              <>
                <p>
                  Does this suggestion correctly describe the hospital’s
                  information?
                </p>
                <div className="decision-buttons">
                  <button
                    className="button primary"
                    disabled={field.id === "date"}
                    onClick={() => onDecision(field.id, "approved")}
                  >
                    <Check size={17} />
                    {field.id === "date"
                      ? "Clarify before approving"
                      : "Approve in preview"}
                  </button>
                  <button
                    className="button secondary"
                    onClick={() => onDecision(field.id, "rejected")}
                  >
                    Send back for correction
                  </button>
                </div>
              </>
            )}
          </div>
        </section>
      </div>
    </>
  );
}

function IdentityReview({
  identity,
  onDecision,
  navigate,
}: {
  identity: "pending" | "linked" | "separate";
  onDecision: (value: "linked" | "separate") => void;
  navigate: (page: Page) => void;
}) {
  const [confirmed, setConfirmed] = useState(false);
  const [note, setNote] = useState("");
  return (
    <>
      <PageHeading
        eyebrow="THE RIGHT RECORDS FOR THE RIGHT PERSON"
        title="Could these be the same person?"
        text="Compare the details carefully. Similar names alone are never enough to link records."
      />
      <div className="match-summary">
        <span className="task-icon lavender">
          <Users size={24} />
        </span>
        <div>
          <strong>
            {identity === "pending"
              ? "One sample match needs a person’s judgment"
              : "This sample match has been reviewed"}
          </strong>
          <p>
            Some details agree, but the name is written differently. Both
            original hospital identities will be preserved.
          </p>
        </div>
        <Badge tone={identity === "pending" ? "amber" : "green"}>
          {identity === "pending"
            ? "Human review needed"
            : "Reviewed in preview"}
        </Badge>
      </div>
      {identity !== "pending" ? (
        <section className="panel">
          <Empty
            title={
              identity === "linked"
                ? "Sample identities linked"
                : "Sample identities kept separate"
            }
            text={
              identity === "linked"
                ? "Both hospital records are preserved. The preview patient journey now includes their history together."
                : "The records remain under separate identities. Leaving uncertain records separate is a valid choice."
            }
          >
            <button
              className="button primary"
              onClick={() => navigate("patients")}
            >
              Explore patient records
              <ArrowRight size={16} />
            </button>
          </Empty>
        </section>
      ) : (
        <>
          <div className="identity-cards">
            {[
              {
                name: "Amina Rahman",
                hospital: "Meghna General Hospital",
                system: "OpenMRS",
                id: "DEMO-A-1042",
              },
              {
                name: "A. Rahman",
                hospital: "Padma Care Hospital",
                system: "OpenEMR",
                id: "DEMO-B-9928",
              },
            ].map((p, index) => (
              <section className="panel identity-card" key={p.id}>
                <div className="section-heading">
                  <Badge>{index ? "Possible match" : "Incoming record"}</Badge>
                  <span className="muted">Sample patient</span>
                </div>
                <div className="person-heading">
                  <span className={`avatar large ${index ? "purple" : ""}`}>
                    AR
                  </span>
                  <div>
                    <h2>{p.name}</h2>
                    <p>{p.hospital}</p>
                  </div>
                </div>
                <dl className="patient-facts">
                  <div>
                    <dt>Date of birth</dt>
                    <dd>
                      3 April 1988 <CheckCircle2 size={15} />
                    </dd>
                  </div>
                  <div>
                    <dt>Gender</dt>
                    <dd>
                      Female <CheckCircle2 size={15} />
                    </dd>
                  </div>
                  <div>
                    <dt>Phone</dt>
                    <dd>{index ? "Not supplied" : "Not shown in preview"}</dd>
                  </div>
                  <div>
                    <dt>National identifier</dt>
                    <dd>Not supplied</dd>
                  </div>
                  <div>
                    <dt>Hospital patient ID</dt>
                    <dd>{p.id}</dd>
                  </div>
                </dl>
                <div className="identity-card-footer">
                  <HospitalIcon size={15} />
                  {p.system} · Original identity retained
                </div>
              </section>
            ))}
          </div>
          <section className="panel match-evidence">
            <div>
              <h2>What the comparison tells us</h2>
              <div className="evidence-line">
                <CheckCircle2 size={18} />
                <span>The date of birth and gender agree.</span>
              </div>
              <div className="evidence-line warning">
                <Info size={18} />
                <span>The given name is abbreviated in one record.</span>
              </div>
              <div className="evidence-line warning">
                <Info size={18} />
                <span>
                  No verified national identifier is available. This is not
                  proof of a match.
                </span>
              </div>
            </div>
            <div className="safe-choice">
              <ShieldCheck size={23} />
              <h3>Unsure? Keep them separate.</h3>
              <p>
                It is better to leave a possible match for follow-up than to
                link the wrong people.
              </p>
            </div>
          </section>
          <section className="panel identity-decision">
            <h2>Your review decision</h2>
            <p>
              Try this with the fictional example. No real patient identities
              will change.
            </p>
            <label className="form-label">
              Why did you make this decision?
              <textarea
                maxLength={500}
                placeholder="Add a short note about the details you checked…"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
              <small>
                Your note helps someone understand the decision later. Use
                sample information only.
              </small>
            </label>
            <label className="check-label">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              <span>
                I have checked the details and confirmed these sample records
                belong to the same person.
              </span>
            </label>
            <div className="decision-buttons">
              <button
                className="button primary"
                disabled={!confirmed || !note.trim()}
                onClick={() => onDecision("linked")}
              >
                <Link2 size={17} />
                Link sample identities
              </button>
              <button
                className="button secondary"
                disabled={!note.trim()}
                onClick={() => onDecision("separate")}
              >
                Keep sample identities separate
              </button>
            </div>
            <p className="decision-hint">
              Add a review note to continue. Linking also requires the
              confirmation above.
            </p>
          </section>
        </>
      )}
    </>
  );
}

function PatientRecords({
  linked,
  navigate,
}: {
  linked: boolean;
  navigate: (page: Page) => void;
}) {
  const [query, setQuery] = useState("");
  const [hospital, setHospital] = useState("all");
  const [kind, setKind] = useState("all");
  const [patient, setPatient] = useState("meghna");
  const matches = (
    linked || patient === "meghna" ? "Amina Rahman" : "A. Rahman"
  )
    .toLowerCase()
    .includes(query.toLowerCase());
  const allowed = timeline.filter(
    (item) =>
      linked ||
      (patient === "meghna"
        ? item.system === "OpenMRS"
        : item.system === "OpenEMR"),
  );
  const visible = allowed.filter(
    (item) =>
      (hospital === "all" || item.system === hospital) &&
      (kind === "all" || item.kind === kind),
  );
  return (
    <>
      <PageHeading
        eyebrow="EVERY VISIT HAS A PLACE IN THE STORY"
        title="A clearer patient journey."
        text="See care in order, with the hospital behind every record always visible."
      />
      <div className="patient-toolbar">
        <label className="search wide">
          <Search size={18} />
          <input
            aria-label="Find a sample patient"
            placeholder="Find a sample patient by name…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        {!linked && (
          <label className="select-label">
            Sample patient
            <select
              value={patient}
              onChange={(e) => {
                setPatient(e.target.value);
                setHospital("all");
              }}
            >
              <option value="meghna">Amina Rahman · Meghna General</option>
              <option value="padma">A. Rahman · Padma Care</option>
            </select>
          </label>
        )}
      </div>
      {!matches ? (
        <Empty
          title="No matching sample patient"
          text="Try “Amina” or “Rahman”. This search contains only the fictional preview records."
        />
      ) : (
        <>
          <section className="panel patient-overview">
            <div className="person-heading">
              <span className="avatar large">AR</span>
              <div>
                <div className="eyebrow">SAMPLE PATIENT</div>
                <h2>
                  {patient === "meghna" || linked
                    ? "Amina Rahman"
                    : "A. Rahman"}
                </h2>
                <p>
                  3 April 1988 <span>·</span> Female <span>·</span>{" "}
                  {linked
                    ? "Combined preview record"
                    : "Single hospital record"}
                </p>
              </div>
            </div>
            <div className="patient-overview-stat">
              <span>Hospitals in this view</span>
              <strong>{linked ? "02" : "01"}</strong>
            </div>
          </section>
          {!linked && (
            <div className="callout">
              <Link2 size={19} />
              <div>
                <strong>These hospital identities are still separate.</strong>
                <p>
                  A second source is added to the same journey only after its
                  patient match is confirmed.
                </p>
              </div>
              <button
                className="text-button"
                onClick={() => navigate("identity")}
              >
                Review the match
                <ArrowRight size={16} />
              </button>
            </div>
          )}
          <div className="history-layout">
            <section>
              <div className="section-heading history-heading">
                <div>
                  <h2>Care timeline</h2>
                  <p>{visible.length} sample records · Most recent first</p>
                </div>
                <div className="timeline-filters">
                  <label>
                    <ListFilter size={15} />
                    <span className="sr-only">Filter by hospital</span>
                    <select
                      value={hospital}
                      onChange={(e) => setHospital(e.target.value)}
                    >
                      <option value="all">All hospitals in view</option>
                      <option value="OpenMRS">Meghna General</option>
                      <option value="OpenEMR">Padma Care</option>
                    </select>
                  </label>
                  <label>
                    <SlidersHorizontal size={15} />
                    <span className="sr-only">Filter by record type</span>
                    <select
                      value={kind}
                      onChange={(e) => setKind(e.target.value)}
                    >
                      <option value="all">All record types</option>
                      <option>Appointment</option>
                      <option>Measurement</option>
                      <option>Lab result</option>
                    </select>
                  </label>
                </div>
              </div>
              <div className="timeline">
                {visible.map((item) => (
                  <article className="timeline-item" key={item.id}>
                    <div className="timeline-marker">
                      {item.icon === "lab" ? (
                        <FlaskConical size={20} />
                      ) : item.icon === "measurement" ? (
                        <Activity size={20} />
                      ) : (
                        <Stethoscope size={20} />
                      )}
                    </div>
                    <div className="panel timeline-card">
                      <div className="timeline-card-top">
                        <Badge>{item.kind}</Badge>
                        <time>{item.date}</time>
                      </div>
                      <div className="record-heading">
                        <h3>{item.title}</h3>
                        <strong>{item.value}</strong>
                      </div>
                      <p>{item.detail}</p>
                      <div className="source-line">
                        <HospitalIcon size={15} />
                        <strong>{item.hospital}</strong>
                        <span>· {item.system}</span>
                      </div>
                      <details className="technical-details">
                        <summary>
                          Where this record came from
                          <ChevronDown size={14} />
                        </summary>
                        <dl>
                          <div>
                            <dt>Original patient ID</dt>
                            <dd>{item.sourceId}</dd>
                          </div>
                          <div>
                            <dt>Original record ID</dt>
                            <dd>{item.recordId}</dd>
                          </div>
                          <div>
                            <dt>Information rules</dt>
                            <dd>{item.mapping}</dd>
                          </div>
                          <div>
                            <dt>Data</dt>
                            <dd>Fictional preview record</dd>
                          </div>
                        </dl>
                      </details>
                    </div>
                  </article>
                ))}
              </div>
              {!visible.length && (
                <Empty
                  title="No records for these filters"
                  text="Try another hospital or record type."
                />
              )}
            </section>
            <aside className="history-context">
              <section className="panel">
                <span className="task-icon green">
                  <Link2 size={21} />
                </span>
                <h3>
                  {linked ? "Linked hospital identities" : "Hospital identity"}
                </h3>
                <p>Original identities are kept intact.</p>
                {(linked
                  ? initialHospitals
                  : initialHospitals.filter((h) => h.id === patient)
                ).map((h) => (
                  <div className="linked-hospital" key={h.id}>
                    <strong>{h.name}</strong>
                    <small>
                      {h.id === "meghna" ? "DEMO-A-1042" : "DEMO-B-9928"}
                    </small>
                    <Badge tone="green">
                      {linked ? "Linked in preview" : "Source record"}
                    </Badge>
                  </div>
                ))}
              </section>
              <div className="history-explainer">
                <ShieldCheck size={23} />
                <h3>The source travels with the record.</h3>
                <p>
                  A combined view never erases a hospital’s original patient ID
                  or the source of a visit, test, or measurement.
                </p>
              </div>
            </aside>
          </div>
        </>
      )}
    </>
  );
}

function Help({ navigate }: { navigate: (page: Page) => void }) {
  return (
    <>
      <PageHeading
        eyebrow="NO TECHNICAL BACKGROUND NEEDED"
        title="Let’s make connected care clear."
        text="A short guide to what DataPulse does, and the decisions you’ll make."
      />
      <section className="guide-intro">
        <span className="task-icon green">
          <BookOpen size={27} />
        </span>
        <div>
          <h2>The big idea is simple.</h2>
          <p>
            Hospitals record information differently. DataPulse helps understand
            those differences, confirms which records belong to the same person,
            and brings their history into one view—with the source always
            attached.
          </p>
        </div>
      </section>
      <div className="help-sections">
        {[
          {
            number: "01",
            title: "Tell us which hospital to connect",
            text: "Start with the hospital name and its record system. A technical colleague handles connection details when secure setup is available.",
            page: "hospitals" as Page,
            action: "Explore hospital setup",
          },
          {
            number: "02",
            title: "Check that information is understood correctly",
            text: "Review simple before-and-after examples. For instance, “F” becomes “Female”. If a field could mean more than one thing, send it back for clarification.",
            page: "fields" as Page,
            action: "Try a field review",
          },
          {
            number: "03",
            title: "Check before linking two patient identities",
            text: "Look at the evidence, note anything that differs, and record why you made your choice. If you are unsure, keep the records separate. Original identities are always retained.",
            page: "identity" as Page,
            action: "Try a patient match",
          },
          {
            number: "04",
            title: "Read the patient’s care journey",
            text: "Browse visits, measurements, and results in date order. Every item shows its original hospital. You can filter the view and open its source details.",
            page: "patients" as Page,
            action: "Explore the patient timeline",
          },
        ].map((step) => (
          <section className="help-step" key={step.number}>
            <span>{step.number}</span>
            <div>
              <h2>{step.title}</h2>
              <p>{step.text}</p>
              <button
                className="text-button"
                onClick={() => navigate(step.page)}
              >
                {step.action}
                <ArrowRight size={16} />
              </button>
            </div>
          </section>
        ))}
      </div>
      <section className="panel glossary">
        <h2>A few words you might see</h2>
        {[
          {
            term: "Field review",
            meaning: "Checking what a piece of hospital information means.",
          },
          {
            term: "Patient matching",
            meaning:
              "Checking whether two hospital identities belong to the same person.",
          },
          {
            term: "Linked identities",
            meaning:
              "Separate hospital identities connected to one person, with the originals preserved.",
          },
          {
            term: "Source",
            meaning:
              "The hospital and record system that originally recorded the information.",
          },
        ].map((item) => (
          <dl key={item.term}>
            <dt>{item.term}</dt>
            <dd>{item.meaning}</dd>
          </dl>
        ))}
      </section>
      <div className="callout">
        <Info size={20} />
        <div>
          <strong>What is available today?</strong>
          <p>
            You can explore these sample workflows and check the live system
            status. Real hospital connections, data reviews, and patient access
            will be introduced with secure permissions in later stages.
          </p>
        </div>
      </div>
    </>
  );
}
