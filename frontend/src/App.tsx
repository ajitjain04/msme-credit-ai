import {
  Activity,
  ArrowLeft,
  ArrowRight,
  BarChart3,
  Bell,
  BookOpen,
  BriefcaseBusiness,
  Building2,
  Check,
  ChevronDown,
  CircleHelp,
  CreditCard,
  Download,
  FileClock,
  FileText,
  Gauge,
  Home,
  IndianRupee,
  Landmark,
  LayoutDashboard,
  Menu,
  Moon,
  RefreshCw,
  Save,
  Scale,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Sun,
  TrendingDown,
  TrendingUp,
  Upload,
  Users,
  WalletCards,
  X,
  Zap,
} from "lucide-react"
import {
  type ButtonHTMLAttributes,
  type ChangeEvent,
  type ComponentType,
  type CSSProperties,
  type FormEvent,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  useEffect,
  useMemo,
  useState,
} from "react"
import { api } from "./api"

type Page = "home" | "business" | "banking" | "tax" | "evaluate" | "portfolio" | "fairness" | "reports" | "settings"

type FormData = {
  companyName: string
  companyId: string
  businessAge: string
  category: string
  state: string
  employees: string
  monthlyInflow: string
  monthlyOutflow: string
  minBalance: string
  volatility: string
  bouncedPayments: string
  accountAge: string
  gstRegistered: boolean
  gstRegularity: string
  gstTurnover: string
  gstDelay: string
  upiShare: string
  posActive: boolean
  digitalScore: string
}

type ApiRecord = Record<string, unknown>

const defaultForm: FormData = {
  companyName: "",
  companyId: "",
  businessAge: "",
  category: "",
  state: "",
  employees: "",
  monthlyInflow: "",
  monthlyOutflow: "",
  minBalance: "",
  volatility: "",
  bouncedPayments: "",
  accountAge: "",
  gstRegistered: true,
  gstRegularity: "",
  gstTurnover: "",
  gstDelay: "",
  upiShare: "",
  posActive: false,
  digitalScore: "",
}

const navItems: {
  id: Page
  label: string
  icon: ComponentType<{ size?: number }>
}[] = [
  { id: "home", label: "Home", icon: Home },
  { id: "business", label: "Business Profile", icon: BriefcaseBusiness },
  { id: "banking", label: "Banking & Cash Flow", icon: Landmark },
  { id: "tax", label: "Tax & Digital Footprint", icon: CreditCard },
  { id: "evaluate", label: "Evaluate", icon: Sparkles },
  { id: "portfolio", label: "Portfolio", icon: LayoutDashboard },
  { id: "fairness", label: "Fairness Audit", icon: Scale },
  { id: "reports", label: "Reports & History", icon: FileClock },
  { id: "settings", label: "Settings", icon: Settings },
]

const states = [
  "Andhra Pradesh",
  "Bihar",
  "Delhi",
  "Gujarat",
  "Haryana",
  "Karnataka",
  "Kerala",
  "Madhya Pradesh",
  "Maharashtra",
  "Punjab",
  "Rajasthan",
  "Tamil Nadu",
  "Telangana",
  "Uttar Pradesh",
  "West Bengal",
]

const terms = [
  {
    title: "Credit Score",
    icon: Gauge,
    text: "A model-generated score from 300–900 representing estimated creditworthiness.",
    detail:
      "Higher scores generally indicate lower estimated credit risk. This is a model output, not a bureau score.",
  },
  {
    title: "Probability of Default",
    icon: Activity,
    text: "Estimated likelihood of default, expressed as a percentage.",
    detail:
      "A 12% probability means the model estimates 12 defaults per 100 similar cases under its modelling assumptions.",
  },
  {
    title: "UPI Transaction Share",
    icon: WalletCards,
    text: "The proportion of relevant transactions represented by UPI.",
    detail:
      "Enter this as a decimal: 0.50 represents 50% of relevant transactions.",
  },
  {
    title: "Digital Payment Adoption Score",
    icon: Zap,
    text: "A dataset feature from 0–100 representing digital-payment adoption.",
    detail:
      "It summarises the breadth and consistency of digital payment usage in the available data.",
  },
  {
    title: "Cash Flow Volatility",
    icon: TrendingUp,
    text: "The degree of fluctuation in business cash flow.",
    detail:
      "Higher volatility can indicate less predictable liquidity, even when average inflows are strong.",
  },
  {
    title: "GST Filing Regularity Score",
    icon: FileText,
    text: "A 0–100 feature representing GST filing regularity.",
    detail:
      "A higher score indicates more consistent filing behaviour in the source dataset.",
  },
  {
    title: "Monthly Inflow and Outflow",
    icon: IndianRupee,
    text: "Money entering and leaving a business account.",
    detail:
      "The difference is monthly net flow, a useful signal of operating liquidity.",
  },
  {
    title: "SHAP Explainability",
    icon: BarChart3,
    text: "Explains how individual input features contribute to a model prediction.",
    detail:
      "SHAP values show direction and relative contribution; they do not prove why an outcome occurred.",
  },
  {
    title: "Disparate Impact Ratio (DIR)",
    icon: Scale,
    text: "A fairness metric comparing favourable outcome rates between groups.",
    detail:
      "Values below 0.80 commonly prompt review under the four-fifths rule, but are not proof of discrimination.",
  },
  {
    title: "Thin-File MSME",
    icon: Building2,
    text: "A business with limited traditional credit history.",
    detail:
      "Alternative signals can add context when bureau or borrowing history is sparse.",
  },
]

function cx(...classes: Array<string | false | undefined>) {
  return classes.filter(Boolean).join(" ")
}

function numberFrom(record: ApiRecord | null, keys: string[]): number | null {
  if (!record) return null
  for (const key of keys) {
    const value = record[key]
    if (typeof value === "number" && Number.isFinite(value)) return value
    if (
      typeof value === "string" &&
      value.trim() &&
      Number.isFinite(Number(value))
    ) {
      return Number(value)
    }
  }
  return null
}

function valueFrom(record: ApiRecord | null, keys: string[]): string | null {
  if (!record) return null
  for (const key of keys) {
    const value = record[key]
    if (typeof value === "string" || typeof value === "number")
      return String(value)
  }
  return null
}

function formatNumber(value: number | null, suffix = "") {
  return value === null
    ? "—"
    : `${new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 }).format(value)}${suffix}`
}

function Button({
  children,
  variant = "primary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost"
}) {
  return (
    <button className={cx("button", `button-${variant}`, className)} {...props}>
      {children}
    </button>
  )
}

function Field({
  label,
  hint,
  error,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  label: string
  hint?: string
  error?: string
}) {
  return (
    <label className="field">
      <span className="field-label">
        {label}
        {hint && <CircleHelp size={14} aria-label={hint} />}
      </span>
      <input className={cx("input", error && "input-error")} {...props} />
      {error && <span className="field-error">{error}</span>}
    </label>
  )
}

function SelectField({
  label,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & {
  label: string
  children: ReactNode
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <span className="select-wrap">
        <select className="input" {...props}>
          {children}
        </select>
        <ChevronDown size={16} />
      </span>
    </label>
  )
}

function Toggle({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  description: string
}) {
  return (
    <label className="toggle-row">
      <span>
        <strong>{label}</strong>
        <small>{description}</small>
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="toggle" aria-hidden="true">
        <span />
      </span>
    </label>
  )
}

function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <header className="page-header">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </header>
  )
}

function EmptyState({
  icon: Icon,
  title,
  text,
}: {
  icon: ComponentType<{ size?: number }>
  title: string
  text: string
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon size={24} />
      </span>
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  )
}

function WizardProgress({ active }: { active: number }) {
  const items = ["Business profile", "Banking & cash flow", "Tax & digital"]
  return (
    <div className="wizard-progress">
      {items.map((item, index) => (
        <div
          className={cx("wizard-step", index + 1 <= active && "active")}
          key={item}
        >
          <span>{index + 1 < active ? <Check size={15} /> : index + 1}</span>
          <div>
            <strong>{item}</strong>
            <small>Step {index + 1} of 3</small>
          </div>
        </div>
      ))}
    </div>
  )
}

function HomePage({
  goTo,
  portfolio,
  loading,
}: {
  goTo: (page: Page) => void
  portfolio: ApiRecord | null
  loading: boolean
}) {
  const kpis = [
    {
      label: "Businesses assessed",
      value: numberFrom(portfolio, ["total_companies", "totalCompanies"]),
      icon: Building2,
    },
    {
      label: "Average credit score",
      value: numberFrom(portfolio, [
        "average_credit_score",
        "avg_credit_score",
      ]),
      icon: Gauge,
    },
    {
      label: "High-risk portfolio",
      value: numberFrom(portfolio, ["high_risk_percentage", "high_risk_pct"]),
      suffix: "%",
      icon: ShieldCheck,
    },
    {
      label: "Total assessments",
      value: numberFrom(portfolio, ["total_assessments", "totalAssessments"]),
      icon: FileText,
    },
  ]

  return (
    <>
      <section className="hero">
        <div className="hero-grid" aria-hidden="true" />
        <div className="hero-copy">
          <span className="eyebrow">
            <Sparkles size={14} /> Explainable credit intelligence
          </span>
          <h1>
            Credit intelligence beyond <span>traditional credit history.</span>
          </h1>
          <p>
            Assess MSME creditworthiness using banking behaviour, tax
            compliance, and digital payment activity — powered by transparent,
            explainable AI.
          </p>
          <div className="hero-actions">
            <Button onClick={() => goTo("business")}>
              Start New Assessment <ArrowRight size={17} />
            </Button>
            <Button variant="secondary" onClick={() => goTo("portfolio")}>
              Explore Portfolio <BarChart3 size={17} />
            </Button>
          </div>
          <div className="trust-row">
            <span>
              <ShieldCheck size={15} /> Explainable predictions
            </span>
            <span>
              <Scale size={15} /> Built-in fairness audit
            </span>
            <span>
              <FileText size={15} /> Decision-ready reports
            </span>
          </div>
        </div>
        <div
          className="hero-visual"
          aria-label="Credit assessment workflow preview"
        >
          <div className="visual-top">
            <span>Assessment preview</span>
            <span className="live-pill">
              <i /> MODEL READY
            </span>
          </div>
          <div className="score-preview">
            <div className="score-orbit">
              <div>
                <small>SCORE RANGE</small>
                <strong>300–900</strong>
                <span>AI assessed</span>
              </div>
            </div>
          </div>
          <div className="signal-list">
            <div>
              <span className="signal-icon positive">
                <TrendingUp size={16} />
              </span>
              <p>
                <strong>Cash flow signals</strong>
                <small>Banking behaviour & stability</small>
              </p>
              <i className="signal-line high" />
            </div>
            <div>
              <span className="signal-icon blue">
                <FileText size={16} />
              </span>
              <p>
                <strong>Compliance signals</strong>
                <small>GST filing consistency</small>
              </p>
              <i className="signal-line medium" />
            </div>
            <div>
              <span className="signal-icon purple">
                <WalletCards size={16} />
              </span>
              <p>
                <strong>Digital footprint</strong>
                <small>UPI & payment adoption</small>
              </p>
              <i className="signal-line low" />
            </div>
          </div>
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Live overview</span>
            <h2>Portfolio at a glance</h2>
          </div>
          <span className="data-note">Sourced from analytics API</span>
        </div>
        <div className="kpi-grid">
          {kpis.map(({ label, value, suffix, icon: Icon }) => (
            <article className="kpi-card" key={label}>
              <span className="kpi-icon">
                <Icon size={19} />
              </span>
              <span className="kpi-label">{label}</span>
              <strong>
                {loading ? (
                  <i className="skeleton" />
                ) : (
                  formatNumber(value, suffix)
                )}
              </strong>
              {!loading && value === null && (
                <small>No portfolio data yet</small>
              )}
            </article>
          ))}
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <span className="eyebrow">How it works</span>
            <h2>From business signals to a transparent decision</h2>
          </div>
        </div>
        <div className="workflow">
          {[
            [Building2, "Business Information"],
            [Landmark, "Banking Signals"],
            [WalletCards, "Tax & Digital Signals"],
            [Sparkles, "AI Evaluation"],
            [FileText, "Credit Report"],
          ].map(([Icon, label], index) => {
            const WorkflowIcon = Icon as ComponentType<{ size?: number }>
            return (
              <div className="workflow-item" key={String(label)}>
                <span>
                  <WorkflowIcon size={19} />
                </span>
                <strong>{String(label)}</strong>
                {index < 4 && <ArrowRight size={15} />}
              </div>
            )
          })}
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <span className="eyebrow">
              <BookOpen size={14} /> Financial learning centre
            </span>
            <h2>Understand the signals behind the score</h2>
            <p>Clear definitions for confident, responsible interpretation.</p>
          </div>
        </div>
        <div className="term-grid">
          {terms.map(({ title, text, detail, icon: Icon }) => (
            <details className="term-card" key={title}>
              <summary>
                <span className="term-icon">
                  <Icon size={19} />
                </span>
                <div>
                  <strong>{title}</strong>
                  <p>{text}</p>
                </div>
                <ChevronDown size={18} />
              </summary>
              <div className="term-detail">{detail}</div>
            </details>
          ))}
        </div>
      </section>
    </>
  )
}

function BusinessPage({ form, update, goTo, save }: FormPageProps) {
  const [errors, setErrors] = useState<Record<string, string>>({})
  const submit = (event: FormEvent) => {
    event.preventDefault()
    const next: Record<string, string> = {}
    if (!form.companyName.trim()) next.companyName = "Company name is required"
    if (!form.businessAge || Number(form.businessAge) <= 0)
      next.businessAge = "Enter a valid business age"
    if (!form.category) next.category = "Select a business category"
    if (!form.state) next.state = "Select a state"
    if (!form.employees || Number(form.employees) < 1)
      next.employees = "Enter at least one employee"
    setErrors(next)
    if (!Object.keys(next).length) goTo("banking")
  }
  return (
    <>
      <PageHeader
        eyebrow="New assessment"
        title="Tell us about the business"
        description="Start with the essential details that help the model contextualise operating signals."
      />
      <WizardProgress active={1} />
      <form onSubmit={submit}>
        <section className="form-card">
          <div className="card-title">
            <span>
              <Building2 size={20} />
            </span>
            <div>
              <h2>Business identity</h2>
              <p>Core registration and operating information.</p>
            </div>
          </div>
          <div className="form-grid">
            <Field
              label="Company name"
              placeholder="e.g. Anand Retail Ventures"
              value={form.companyName}
              onChange={(e) => update("companyName", e.target.value)}
              error={errors.companyName}
            />
            <Field
              label="Existing company ID (optional)"
              placeholder="Use an existing backend ID"
              value={form.companyId}
              onChange={(e) => update("companyId", e.target.value)}
            />
            <Field
              label="Business age in years"
              type="number"
              min="0.1"
              step="0.1"
              placeholder="e.g. 5"
              value={form.businessAge}
              onChange={(e) => update("businessAge", e.target.value)}
              error={errors.businessAge}
            />
            <SelectField
              label="Business category"
              value={form.category}
              onChange={(e) => update("category", e.target.value)}
            >
              <option value="">Select category</option>
              {["Retail", "Trading", "Services", "Manufacturing", "Food"].map(
                (item) => (
                  <option key={item}>{item}</option>
                ),
              )}
            </SelectField>
            <SelectField
              label="State"
              value={form.state}
              onChange={(e) => update("state", e.target.value)}
            >
              <option value="">Select state</option>
              {states.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </SelectField>
            <Field
              label="Employee count"
              type="number"
              min="1"
              step="1"
              placeholder="e.g. 18"
              value={form.employees}
              onChange={(e) => update("employees", e.target.value)}
              error={errors.employees}
            />
          </div>
        </section>
        <FormActions save={save} nextLabel="Continue to banking" />
      </form>
    </>
  )
}

type FormPageProps = {
  form: FormData
  update: <K extends keyof FormData>(key: K, value: FormData[K]) => void
  goTo: (page: Page) => void
  save: () => void
}

function FormActions({
  save,
  back,
  nextLabel,
  nextType = "submit",
  onNext,
}: {
  save: () => void
  back?: () => void
  nextLabel: string
  nextType?: "submit" | "button"
  onNext?: () => void
}) {
  return (
    <div className="form-actions">
      <div>
        {back && (
          <Button type="button" variant="ghost" onClick={back}>
            <ArrowLeft size={17} /> Back
          </Button>
        )}
      </div>
      <div>
        <Button type="button" variant="secondary" onClick={save}>
          <Save size={16} /> Save progress
        </Button>
        <Button type={nextType} onClick={onNext}>
          {nextLabel} <ArrowRight size={17} />
        </Button>
      </div>
    </div>
  )
}

function BankingPage({ form, update, goTo, save }: FormPageProps) {
  const [error, setError] = useState("")
  const [uploading, setUploading] = useState(false)
  const [uploadNote, setUploadNote] = useState<{ ok: boolean; text: string } | null>(null)

  // Sends the chosen CSV to the backend and copies the 5 parsed values into
  // the form. The user can still edit every field afterwards.
  const handleStatementUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setUploading(true)
    setUploadNote(null)
    try {
      const parsed = await api.parseBankStatement(file)
      update("monthlyInflow", String(parsed.avg_monthly_inflow))
      update("monthlyOutflow", String(parsed.avg_monthly_outflow))
      update("minBalance", String(parsed.min_ending_balance_avg))
      update("bouncedPayments", String(parsed.bounce_count_last_6m))
      update("accountAge", String(parsed.account_vintage_months))
      setUploadNote({
        ok: true,
        text: "Auto-filled 5 fields from your statement — review before submitting.",
      })
    } catch (reason) {
      setUploadNote({
        ok: false,
        text: reason instanceof Error ? reason.message : "The statement could not be read.",
      })
    } finally {
      setUploading(false)
      event.target.value = "" // lets the same file be chosen again
    }
  }
  const netFlow =
    (Number(form.monthlyInflow) || 0) - (Number(form.monthlyOutflow) || 0)
  const total = Math.max(
    Number(form.monthlyInflow) || 0,
    Number(form.monthlyOutflow) || 0,
    1,
  )
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (Number(form.accountAge) > Number(form.businessAge) * 12) {
      setError("Bank account age cannot exceed the business age in months.")
      return
    }
    setError("")
    goTo("tax")
  }
  return (
    <>
      <PageHeader
        eyebrow="New assessment"
        title="Map the cash flow pattern"
        description="Add account behaviour and liquidity signals. Values should reflect recent normal operating activity."
      />
      <WizardProgress active={2} />
      <form onSubmit={submit}>
        <section className="form-card statement-upload">
          <div className="card-title">
            <span>
              <Upload size={20} />
            </span>
            <div>
              <h2>Upload bank statement (CSV)</h2>
              <p>
                Optional. Columns: date (YYYY-MM-DD), description, debit,
                credit, balance. Auto-fills the banking fields below.
              </p>
            </div>
          </div>
          <input
            type="file"
            accept=".csv,text/csv"
            disabled={uploading}
            aria-label="Upload bank statement CSV"
            onChange={handleStatementUpload}
          />
          {uploadNote && (
            <div className={uploadNote.ok ? "inline-note" : "field-error"}>
              {uploadNote.text}
            </div>
          )}
        </section>
        <div className="split-layout">
          <section className="form-card">
            <div className="card-title">
              <span>
                <TrendingUp size={20} />
              </span>
              <div>
                <h2>Cash flow</h2>
                <p>Monthly account activity and consistency.</p>
              </div>
            </div>
            <div className="form-grid">
              <Field
                required
                label="Average monthly inflow (₹)"
                type="number"
                min="0"
                step="0.01"
                placeholder="e.g. 850000"
                value={form.monthlyInflow}
                onChange={(e) => update("monthlyInflow", e.target.value)}
              />
              <Field
                required
                label="Average monthly outflow (₹)"
                type="number"
                min="0"
                step="0.01"
                placeholder="e.g. 620000"
                value={form.monthlyOutflow}
                onChange={(e) => update("monthlyOutflow", e.target.value)}
              />
              <Field
                required
                label="Average minimum bank balance (₹)"
                type="number"
                min="0"
                step="0.01"
                placeholder="e.g. 125000"
                value={form.minBalance}
                onChange={(e) => update("minBalance", e.target.value)}
              />
              <Field
                required
                label="Cash flow volatility"
                hint="Degree of fluctuation in business cash flow."
                type="number"
                min="0"
                step="0.01"
                placeholder="Backend feature value"
                value={form.volatility}
                onChange={(e) => update("volatility", e.target.value)}
              />
            </div>
          </section>
          <aside className="cash-card">
            <div>
              <span className="eyebrow">Live cash flow view</span>
              <h3>Monthly net position</h3>
            </div>
            <strong className={netFlow < 0 ? "negative" : ""}>
              {netFlow < 0 ? "−" : "+"} ₹
              {Math.abs(netFlow).toLocaleString("en-IN")}
            </strong>
            <p>
              {netFlow >= 0
                ? "Inflow currently exceeds outflow."
                : "Outflow currently exceeds inflow."}
            </p>
            <div className="cash-bars">
              <div>
                <span>Inflow</span>
                <i>
                  <b
                    style={{
                      width: `${((Number(form.monthlyInflow) || 0) / total) * 100}%`,
                    }}
                  />
                </i>
                <strong>
                  ₹{(Number(form.monthlyInflow) || 0).toLocaleString("en-IN")}
                </strong>
              </div>
              <div className="outflow">
                <span>Outflow</span>
                <i>
                  <b
                    style={{
                      width: `${((Number(form.monthlyOutflow) || 0) / total) * 100}%`,
                    }}
                  />
                </i>
                <strong>
                  ₹{(Number(form.monthlyOutflow) || 0).toLocaleString("en-IN")}
                </strong>
              </div>
            </div>
          </aside>
        </div>
        <section className="form-card">
          <div className="card-title">
            <span>
              <Landmark size={20} />
            </span>
            <div>
              <h2>Account stability</h2>
              <p>Signals reflecting payment discipline and banking tenure.</p>
            </div>
          </div>
          <div className="form-grid">
            <Field
              required
              label="Bounced payments in last 6 months"
              hint="Count of returned or failed scheduled payments."
              type="number"
              min="0"
              step="1"
              value={form.bouncedPayments}
              onChange={(e) => update("bouncedPayments", e.target.value)}
            />
            <Field
              required
              label="Bank account age in months"
              type="number"
              min="0"
              step="1"
              value={form.accountAge}
              onChange={(e) => update("accountAge", e.target.value)}
              error={error}
            />
          </div>
        </section>
        <FormActions
          save={save}
          back={() => goTo("business")}
          nextLabel="Continue to tax & digital"
        />
      </form>
    </>
  )
}

function TaxPage({ form, update, goTo, save }: FormPageProps) {
  return (
    <>
      <PageHeader
        eyebrow="New assessment"
        title="Complete the financial footprint"
        description="Add compliance and payment adoption signals before reviewing the assessment."
      />
      <WizardProgress active={3} />
      <section className="form-card">
        <div className="card-title">
          <span>
            <FileText size={20} />
          </span>
          <div>
            <h2>Tax & compliance</h2>
            <p>GST registration and filing behaviour.</p>
          </div>
        </div>
        <Toggle
          checked={form.gstRegistered}
          onChange={(value) => update("gstRegistered", value)}
          label="GST registered"
          description="Enable to include available GST compliance signals."
        />
        {form.gstRegistered ? (
          <div className="form-grid conditional-fields">
            <Field
              required
              label="GST filing regularity score"
              type="number"
              min="0"
              max="100"
              step="any"
              value={form.gstRegularity}
              onChange={(e) => update("gstRegularity", e.target.value)}
            />
            <Field
              required
              label="Annual GST turnover (₹)"
              type="number"
              min="0"
              step="0.01"
              value={form.gstTurnover}
              onChange={(e) => update("gstTurnover", e.target.value)}
            />
            <Field
              required
              label="Average GST filing delay (days)"
              type="number"
              min="0"
              step="any"
              value={form.gstDelay}
              onChange={(e) => update("gstDelay", e.target.value)}
            />
          </div>
        ) : (
          <div className="inline-note">
            <CircleHelp size={17} /> GST-related fields will be omitted from the
            evaluation payload.
          </div>
        )}
      </section>
      <section className="form-card">
        <div className="card-title">
          <span>
            <WalletCards size={20} />
          </span>
          <div>
            <h2>Digital footprint</h2>
            <p>Digital payment usage and infrastructure.</p>
          </div>
        </div>
        <div className="form-grid">
          <Field
            required
            label="UPI transaction share (0–1)"
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={form.upiShare}
            onChange={(e) => update("upiShare", e.target.value)}
          />
          <div className="scale-feedback">
            <span>UPI share</span>
            <strong>
              {Math.min(
                100,
                Math.max(0, Number(form.upiShare) * 100 || 0),
              ).toFixed(0)}
              %
            </strong>
            <i>
              <b
                style={{
                  width: `${Math.min(100, Math.max(0, Number(form.upiShare) * 100 || 0))}%`,
                }}
              />
            </i>
          </div>
          <Field
            required
            label="Digital payment adoption score"
            type="number"
            min="0"
            max="100"
            step="any"
            value={form.digitalScore}
            onChange={(e) => update("digitalScore", e.target.value)}
          />
          <div className="scale-feedback">
            <span>Adoption maturity</span>
            <strong>{form.digitalScore || "0"} / 100</strong>
            <i>
              <b
                style={{
                  width: `${Math.min(100, Math.max(0, Number(form.digitalScore) || 0))}%`,
                }}
              />
            </i>
          </div>
        </div>
        <Toggle
          checked={form.posActive}
          onChange={(value) => update("posActive", value)}
          label="POS terminal active"
          description="The business currently accepts card payments through a POS terminal."
        />
      </section>
      <FormActions
        save={save}
        back={() => goTo("banking")}
        nextLabel="Review & Evaluate Business"
        nextType="button"
        onNext={() => goTo("evaluate")}
      />
    </>
  )
}

function ReviewSection({
  title,
  icon: Icon,
  rows,
  edit,
}: {
  title: string
  icon: ComponentType<{ size?: number }>
  rows: [string, string][]
  edit: () => void
}) {
  return (
    <section className="review-card">
      <div className="review-head">
        <span>
          <Icon size={18} /> {title}
        </span>
        <Button variant="ghost" onClick={edit}>
          Edit
        </Button>
      </div>
      <div className="review-grid">
        {rows.map(([label, value]) => (
          <div key={label}>
            <small>{label}</small>
            <strong>{value || "Not provided"}</strong>
          </div>
        ))}
      </div>
    </section>
  )
}

// Field names here must match backend/schemas.py's MSMEInput EXACTLY --
// the Figma Make export invented its own plausible-looking names (e.g.
// "business_age_years", "average_monthly_inflow", "gst_registered") that
// don't exist on the real model at all, so every evaluate submission was
// failing Pydantic's required-field validation (422) before this fix.
function buildPayload(form: FormData): ApiRecord {
  const payload: ApiRecord = {
    company_name: form.companyName,
    age_of_business_years: Number(form.businessAge),
    // category_encodings.json's keys are lowercase ("retail", "trading",
    // ...); the dropdown shows Title Case for readability, so lowercase
    // it here before sending.
    business_category: form.category.toLowerCase(),
    state: form.state,
    employee_count: Number(form.employees),
    avg_monthly_inflow: Number(form.monthlyInflow),
    avg_monthly_outflow: Number(form.monthlyOutflow),
    min_ending_balance_avg: Number(form.minBalance),
    cash_flow_volatility: Number(form.volatility),
    bounce_count_last_6m: Number(form.bouncedPayments),
    account_vintage_months: Number(form.accountAge),
    has_gst_registration: form.gstRegistered,
    upi_transaction_volume_ratio: Number(form.upiShare),
    pos_terminal_active_status: form.posActive,
    digital_payment_adoption_score: Number(form.digitalScore),
  }
  if (form.companyId) payload.company_id = form.companyId
  // has_gst_registration=False requires these 3 fields to be OMITTED
  // (null) -- backend/schemas.py's validate_gst_fields_match_registration()
  // rejects the request (422) if they're present but registration is
  // false, or if they're missing while registration is true.
  if (form.gstRegistered) {
    payload.gst_filing_regularity_score = Number(form.gstRegularity)
    payload.annual_turnover_gst = Number(form.gstTurnover)
    payload.gst_filing_delay_days_avg = Number(form.gstDelay)
  }
  return payload
}

type ShapFactor = {
  name: string
  value: string
  contribution: number
  explanation?: string
}

function extractShap(result: ApiRecord): ShapFactor[] {
  // backend/schemas.py's EvaluateResponse splits SHAP drivers into 2
  // arrays (top_positive_drivers / top_negative_drivers), not 1 combined
  // list under a key like "shap_values" -- merge them here. Each item is
  // a ShapDriver: {feature, value (nullable), shap_value, display_value}.
  const positive = Array.isArray(result.top_positive_drivers)
    ? result.top_positive_drivers
    : []
  const negative = Array.isArray(result.top_negative_drivers)
    ? result.top_negative_drivers
    : []
  const raw =
    positive.length || negative.length
      ? [...positive, ...negative]
      : result.shap_values ||
        result.shap_explanations ||
        result.feature_contributions ||
        result.explanations
  if (Array.isArray(raw)) {
    return raw.flatMap((item) => {
      if (!item || typeof item !== "object") return []
      const row = item as ApiRecord
      const contribution = numberFrom(row, [
        "shap_value",
        "contribution",
        "value",
      ])
      if (contribution === null) return []
      return [
        {
          name:
            valueFrom(row, ["feature", "feature_name", "name"]) || "Feature",
          // display_value is ALWAYS already decoded/formatted server-side
          // (e.g. "retail" instead of "2.00", "Not available (GST not
          // registered)" instead of a crash) -- prefer it over the raw
          // "value", which can be null. Same fix already applied in the
          // old Next.js frontend.
          value:
            valueFrom(row, ["display_value", "feature_value", "input_value"]) ||
            "—",
          contribution,
          explanation:
            valueFrom(row, ["explanation", "description"]) || undefined,
        },
      ]
    })
  }
  if (raw && typeof raw === "object") {
    return Object.entries(raw as ApiRecord).flatMap(([name, value]) => {
      if (typeof value === "number")
        return [{ name, value: "—", contribution: value }]
      if (value && typeof value === "object") {
        const row = value as ApiRecord
        const contribution = numberFrom(row, [
          "contribution",
          "shap_value",
          "value",
        ])
        if (contribution !== null)
          return [
            {
              name,
              value: valueFrom(row, ["feature_value", "input_value"]) || "—",
              contribution,
            },
          ]
      }
      return []
    })
  }
  return []
}

function EvaluatePage({
  form,
  goTo,
}: {
  form: FormData
  goTo: (page: Page) => void
}) {
  const [confirmed, setConfirmed] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ApiRecord | null>(null)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")

  const run = async () => {
    setLoading(true)
    setError("")
    setResult(null)
    try {
      setResult(await api.evaluate(buildPayload(form)))
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The assessment could not be completed.",
      )
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <AssessmentLoader />
  if (result) {
    const score = numberFrom(result, ["credit_score", "score"])
    const probabilityRaw = numberFrom(result, [
      "default_probability",
      "probability_of_default",
      "pd",
    ])
    const probability =
      probabilityRaw !== null && probabilityRaw <= 1
        ? probabilityRaw * 100
        : probabilityRaw
    const backendRisk = valueFrom(result, [
      "risk_classification",
      "risk_band",
      "risk_category",
    ])
    const risk =
      backendRisk ||
      (score === null
        ? "Unavailable"
        : score >= 750
          ? "Low Risk"
          : score >= 600
            ? "Medium Risk"
            : "High Risk")
    const companyId =
      valueFrom(result, ["company_id", "business_id", "id"]) || form.companyId
    const factors = extractShap(result).sort(
      (a, b) => Math.abs(b.contribution) - Math.abs(a.contribution),
    )
    // Plain-English paragraph from model/explanation_text.py (rule-based).
    const overallSummary = valueFrom(result, ["overall_summary"])
    const maxContribution = Math.max(
      ...factors.map((item) => Math.abs(item.contribution)),
      0.001,
    )
    const download = async () => {
      if (!companyId) return
      setNotice("")
      try {
        await api.downloadReport(companyId)
        setNotice("PDF report downloaded successfully.")
      } catch (reason) {
        setNotice(
          reason instanceof Error ? reason.message : "Report download failed.",
        )
      }
    }
    return (
      <>
        <PageHeader
          eyebrow="Assessment complete"
          title="Credit assessment"
          description="Model output, contributing signals, and decision context in one transparent view."
          action={
            <span
              className={cx("risk-badge", risk.toLowerCase().replace(" ", "-"))}
            >
              <i /> {risk}
            </span>
          }
        />
        <div className="result-hero">
          <section className="score-card">
            <div
              className="gauge-ring"
              style={
                {
                  "--score":
                    score === null
                      ? 0
                      : Math.max(0, Math.min(100, ((score - 300) / 600) * 100)),
                } as CSSProperties
              }
            >
              <div>
                <small>CREDIT SCORE</small>
                <strong>{score ?? "—"}</strong>
                <span>out of 900</span>
              </div>
            </div>
            <div>
              <span className="eyebrow">Model assessment</span>
              <h2>{risk}</h2>
              <p>
                Based on the submitted banking, compliance, and digital payment
                signals.
              </p>
            </div>
          </section>
          <section className="probability-card">
            <span className="eyebrow">Probability of default</span>
            <strong>
              {probability === null ? "—" : `${probability.toFixed(1)}%`}
            </strong>
            <div className="probability-track">
              <i
                style={{
                  left: `${Math.max(0, Math.min(100, probability || 0))}%`,
                }}
              />
            </div>
            <div className="probability-labels">
              <span>Low &lt;20%</span>
              <span>Medium 20–50%</span>
              <span>High &gt;50%</span>
            </div>
            <p>
              This is a statistical estimate, not a certainty or lending
              decision.
            </p>
          </section>
        </div>
        <div className="metric-strip">
          <div>
            <small>Credit score</small>
            <strong>{score ?? "Unavailable"}</strong>
          </div>
          <div>
            <small>Default probability</small>
            <strong>
              {probability === null
                ? "Unavailable"
                : `${probability.toFixed(1)}%`}
            </strong>
          </div>
          <div>
            <small>Risk band</small>
            <strong>{risk}</strong>
          </div>
          <div>
            <small>Business ID</small>
            <strong>{companyId || "Not returned"}</strong>
          </div>
          <div>
            <small>Assessment date</small>
            <strong>
              {valueFrom(result, [
                "assessed_at",
                "assessment_date",
                "created_at",
                "timestamp",
              ]) || "Not returned"}
            </strong>
          </div>
        </div>
        <section className="explain-card">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Explainable AI</span>
              <h2>What influenced this assessment</h2>
              <p>
                Contributions are displayed exactly as returned by the
                evaluation API.
              </p>
            </div>
            <span className="legend">
              <i className="reduce" /> Risk reducing <i className="increase" />{" "}
              Risk increasing
            </span>
          </div>
          {overallSummary ? (
            <p className="overall-summary">{overallSummary}</p>
          ) : null}
          {factors.length ? (
            <div className="shap-list">
              {factors.map((factor) => {
                const width = `${(Math.abs(factor.contribution) / maxContribution) * 50}%`
                return (
                  <div
                    className="shap-row"
                    key={`${factor.name}-${factor.contribution}`}
                  >
                    <div>
                      <strong>{factor.name.replaceAll("_", " ")}</strong>
                      <small>Input: {factor.value}</small>
                      {factor.explanation ? (
                        <p className="shap-explanation">{factor.explanation}</p>
                      ) : null}
                    </div>
                    <div className="shap-axis">
                      <i
                        className={
                          factor.contribution < 0 ? "reduce" : "increase"
                        }
                        style={
                          factor.contribution < 0
                            ? { right: "50%", width }
                            : { left: "50%", width }
                        }
                      />
                      <span />
                    </div>
                    <strong
                      className={factor.contribution < 0 ? "teal" : "coral"}
                    >
                      {factor.contribution > 0 ? "+" : ""}
                      {factor.contribution.toFixed(3)}
                    </strong>
                  </div>
                )
              })}
            </div>
          ) : (
            <EmptyState
              icon={BarChart3}
              title="No explanation data returned"
              text="The assessment completed, but this API response did not include SHAP values or feature explanations."
            />
          )}
        </section>
        <section className="summary-card">
          <div>
            <span>
              <Building2 size={17} />
            </span>
            <h3>Input data</h3>
            <p>
              Business profile, cash flow, tax compliance, and digital footprint
              submitted for this assessment.
            </p>
          </div>
          <div>
            <span>
              <Sparkles size={17} />
            </span>
            <h3>Prediction</h3>
            <p>
              The score and default probability are model outputs from the
              connected API.
            </p>
          </div>
          <div>
            <span>
              <BarChart3 size={17} />
            </span>
            <h3>Explanation</h3>
            <p>
              SHAP contributions describe model influence, not causal
              relationships.
            </p>
          </div>
          <div>
            <span>
              <CircleHelp size={17} />
            </span>
            <h3>Limitations</h3>
            <p>
              Use with policy review, data-quality checks, and qualified human
              judgement.
            </p>
          </div>
        </section>
        {notice && <div className="toast">{notice}</div>}
        <div className="result-actions">
          <Button onClick={download} disabled={!companyId}>
            <Download size={17} /> Download Credit Assessment PDF
          </Button>
          <Button variant="secondary" onClick={() => setResult(null)}>
            <RefreshCw size={16} /> Re-evaluate
          </Button>
          <Button variant="ghost" onClick={() => goTo("business")}>
            Edit information
          </Button>
          <Button variant="ghost" onClick={() => goTo("home")}>
            Return home
          </Button>
        </div>
      </>
    )
  }

  return (
    <>
      <PageHeader
        eyebrow="Review & evaluate"
        title="Confirm assessment inputs"
        description="Review each section carefully. Predictions are generated only after you explicitly run the assessment."
      />
      <div className="review-stack">
        <ReviewSection
          title="Business profile"
          icon={Building2}
          edit={() => goTo("business")}
          rows={[
            ["Company", form.companyName],
            ["Category", form.category],
            ["State", form.state],
            ["Business age", form.businessAge && `${form.businessAge} years`],
            ["Employees", form.employees],
          ]}
        />
        <ReviewSection
          title="Banking & cash flow"
          icon={Landmark}
          edit={() => goTo("banking")}
          rows={[
            [
              "Monthly inflow",
              form.monthlyInflow &&
                `₹${Number(form.monthlyInflow).toLocaleString("en-IN")}`,
            ],
            [
              "Monthly outflow",
              form.monthlyOutflow &&
                `₹${Number(form.monthlyOutflow).toLocaleString("en-IN")}`,
            ],
            [
              "Minimum balance",
              form.minBalance &&
                `₹${Number(form.minBalance).toLocaleString("en-IN")}`,
            ],
            ["Account age", form.accountAge && `${form.accountAge} months`],
          ]}
        />
        <ReviewSection
          title="Tax & digital footprint"
          icon={WalletCards}
          edit={() => goTo("tax")}
          rows={[
            [
              "GST status",
              form.gstRegistered ? "Registered" : "Not registered",
            ],
            [
              "GST regularity",
              form.gstRegistered
                ? `${form.gstRegularity || "—"} / 100`
                : "Not applicable",
            ],
            ["UPI share", form.upiShare && `${Number(form.upiShare) * 100}%`],
            [
              "Digital adoption",
              form.digitalScore && `${form.digitalScore} / 100`,
            ],
          ]}
        />
      </div>
      <label className="confirmation">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(event) => setConfirmed(event.target.checked)}
        />
        <span>
          <Check size={14} />
        </span>
        <p>
          <strong>I confirm these inputs are complete and accurate.</strong>
          <small>
            I understand that this prototype assessment is not a real lending
            decision.
          </small>
        </p>
      </label>
      {error && (
        <div className="error-banner">
          <CircleHelp size={18} />
          <div>
            <strong>Assessment failed</strong>
            <p>{error}</p>
          </div>
        </div>
      )}
      <div className="evaluate-action">
        <Button disabled={!confirmed || !form.companyName} onClick={run}>
          <Sparkles size={18} /> Run Credit Assessment
        </Button>
        <small>
          The backend will process the submitted signals. No prediction is
          generated before this step.
        </small>
      </div>
    </>
  )
}

function AssessmentLoader() {
  return (
    <div className="assessment-loader">
      <div className="loader-orbit">
        <Sparkles size={28} />
      </div>
      <span className="eyebrow">Secure model processing</span>
      <h1>Evaluating credit signals</h1>
      <p>
        Analysing banking behaviour, GST compliance, and digital payment
        activity…
      </p>
      <div className="loader-steps">
        <span className="done">
          <Check size={14} /> Validating inputs
        </span>
        <span className="active">
          <Activity size={14} /> Running model
        </span>
        <span>
          <BarChart3 size={14} /> Building explanations
        </span>
      </div>
    </div>
  )
}

function PortfolioPage() {
  const [data, setData] = useState<ApiRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const load = async () => {
    setLoading(true)
    setError("")
    try {
      setData(await api.portfolio())
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Unable to load portfolio.",
      )
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => {
    void load()
  }, [])
  // backend/schemas.py's PortfolioAnalyticsResponse has no
  // "risk_distribution"/"risk_categories" sub-object -- the 3 risk-band
  // counts are plain top-level fields (low_risk_count/medium_risk_count/
  // high_risk_count). Keys here are "low_risk"/"medium_risk"/"high_risk"
  // (not "Low Risk" etc.) specifically because src/index.css's
  // .chart-legend/.bar-chart selectors target ".low_risk"/".medium_risk"/
  // ".high_risk" classes (via key.toLowerCase()) for their colors.
  const risk: [string, number][] = data
    ? [
        ["low_risk", numberFrom(data, ["low_risk_count"]) ?? 0],
        ["medium_risk", numberFrom(data, ["medium_risk_count"]) ?? 0],
        ["high_risk", numberFrom(data, ["high_risk_count"]) ?? 0],
      ]
    : []
  const total = risk.reduce((sum, [, value]) => sum + value, 0)
  return (
    <>
      <PageHeader
        eyebrow="Enterprise analytics"
        title="Portfolio Intelligence"
        description="A live view of portfolio composition and assessed risk from the connected analytics service."
        action={
          <Button variant="secondary" onClick={load} disabled={loading}>
            <RefreshCw size={16} /> Refresh data
          </Button>
        }
      />
      {error && (
        <div className="error-banner">
          <CircleHelp size={18} />
          <div>
            <strong>Portfolio unavailable</strong>
            <p>{error}</p>
          </div>
        </div>
      )}
      {loading ? (
        <div className="panel-loader">
          <RefreshCw size={24} />
          <span>Loading portfolio analytics…</span>
        </div>
      ) : data ? (
        <>
          <div className="kpi-grid">
            {[
              [
                "Total companies",
                numberFrom(data, ["total_companies", "totalCompanies"]),
                Building2,
              ],
              [
                "Total assessments",
                numberFrom(data, ["total_assessments", "totalAssessments"]),
                FileText,
              ],
              [
                "Average credit score",
                numberFrom(data, ["average_credit_score", "avg_credit_score"]),
                Gauge,
              ],
              [
                "High-risk percentage",
                numberFrom(data, ["high_risk_percentage", "high_risk_pct"]),
                ShieldCheck,
                "%",
              ],
            ].map(([label, value, Icon, suffix]) => {
              const MetricIcon = Icon as ComponentType<{ size?: number }>
              return (
                <article className="kpi-card" key={String(label)}>
                  <span className="kpi-icon">
                    <MetricIcon size={19} />
                  </span>
                  <span className="kpi-label">{String(label)}</span>
                  <strong>
                    {formatNumber(value as number | null, String(suffix || ""))}
                  </strong>
                </article>
              )
            })}
          </div>
          <div className="analytics-grid">
            <section className="chart-card">
              <div className="card-heading">
                <div>
                  <h2>Risk distribution</h2>
                  <p>Companies by model risk category</p>
                </div>
              </div>
              {risk.length ? (
                <div className="donut-layout">
                  <div
                    className="donut"
                    style={
                      {
                        "--low": `${((risk.find(([key]) => key.toLowerCase().includes("low"))?.[1] || 0) / total) * 100}%`,
                        "--medium": `${(((risk.find(([key]) => key.toLowerCase().includes("medium"))?.[1] || 0) + (risk.find(([key]) => key.toLowerCase().includes("low"))?.[1] || 0)) / total) * 100}%`,
                      } as CSSProperties
                    }
                  >
                    <span>
                      <strong>{total}</strong>
                      <small>companies</small>
                    </span>
                  </div>
                  <div className="chart-legend">
                    {risk.map(([key, value]) => (
                      <div key={key}>
                        <i className={key.toLowerCase()} />
                        <span>{key.replaceAll("_", " ")}</span>
                        <strong>{value}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <EmptyState
                  icon={BarChart3}
                  title="No distribution returned"
                  text="Risk category data is not available in this analytics response."
                />
              )}
            </section>
            <section className="chart-card">
              <div className="card-heading">
                <div>
                  <h2>Risk category comparison</h2>
                  <p>Relative portfolio composition</p>
                </div>
              </div>
              {risk.length ? (
                <div className="bar-chart">
                  {risk.map(([key, value]) => (
                    <div key={key}>
                      <span>{key.replaceAll("_", " ")}</span>
                      <i>
                        <b
                          className={key.toLowerCase()}
                          style={{
                            width: `${(value / Math.max(...risk.map(([, count]) => count))) * 100}%`,
                          }}
                        />
                      </i>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon={Activity}
                  title="Nothing to compare yet"
                  text="Complete assessments to populate risk categories."
                />
              )}
            </section>
          </div>
          <SupportedBreakdowns data={data} />
        </>
      ) : (
        !error && (
          <EmptyState
            icon={LayoutDashboard}
            title="Portfolio is empty"
            text="Analytics will appear after the backend has recorded assessments."
          />
        )
      )}
    </>
  )
}

function SupportedBreakdowns({ data }: { data: ApiRecord }) {
  const possible = [
    [
      "Business category",
      data.business_category_breakdown || data.category_breakdown,
    ],
    ["State", data.state_breakdown],
    [
      "Credit score distribution",
      data.credit_score_distribution || data.score_distribution,
    ],
  ] as [string, unknown][]
  const valid = possible.filter(
    ([, value]) => value && typeof value === "object",
  )
  if (!valid.length)
    return (
      <section className="form-card">
        <EmptyState
          icon={BarChart3}
          title="Additional breakdowns not supported"
          text="This API response does not currently include category, state, or credit score distributions."
        />
      </section>
    )
  return (
    <div className="breakdown-grid">
      {valid.map(([title, value]) => {
        const rows = Object.entries(value as ApiRecord).filter(
          ([, count]) => typeof count === "number",
        ) as [string, number][]
        const max = Math.max(...rows.map(([, count]) => count), 1)
        return (
          <section className="chart-card" key={title}>
            <div className="card-heading">
              <h2>{title}</h2>
            </div>
            <div className="mini-bars">
              {rows.map(([label, count]) => (
                <div key={label}>
                  <span>{label.replaceAll("_", " ")}</span>
                  <i>
                    <b style={{ width: `${(count / max) * 100}%` }} />
                  </i>
                  <strong>{count}</strong>
                </div>
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}

function FairnessPage() {
  const [data, setData] = useState<ApiRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const load = async () => {
    setLoading(true)
    setError("")
    try {
      setData(await api.fairness())
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Unable to load fairness audit.",
      )
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => {
    void load()
  }, [])
  // backend/schemas.py's FairnessAuditResponse has none of "groups"/
  // "group_metrics"/"disparate_impact_ratios"/"audit_results" -- the real
  // field is "audits", a list of FairnessCohortAudit objects
  // ({cohort_dimension, cohort_value, dir_value, group_actual_default_rate,
  // cohort_size, cohort_size_with_known_outcome, flagged_low_dir}). This
  // was previously a TypeScript syntax error too (missing separators
  // between the object type's members), which would have failed to build.
  const rows = useMemo<
    { group: string; dir: number; sample?: number; defaultRate?: number }[]
  >(() => {
    if (!data) return []
    const raw = Array.isArray(data.audits)
      ? data.audits
      : data.groups ||
        data.group_metrics ||
        data.disparate_impact_ratios ||
        data.audit_results
    if (Array.isArray(raw))
      return raw.flatMap((item) => {
        if (!item || typeof item !== "object") return []
        const row = item as ApiRecord
        const dir = numberFrom(row, [
          "dir_value",
          "disparate_impact_ratio",
          "dir",
          "ratio",
        ])
        if (dir === null) return []
        const dimension = valueFrom(row, ["cohort_dimension"])
        const value = valueFrom(row, [
          "cohort_value",
          "group",
          "category",
          "state",
          "name",
        ])
        return [
          {
            group: dimension && value ? `${dimension}: ${value}` : value || "Group",
            dir,
            sample:
              numberFrom(row, ["cohort_size", "sample_size", "count", "n"]) ??
              undefined,
            // Never show DIR alone (backend/main.py's own docstring: "a
            // flagged cohort is a prompt to look at its actual default
            // rate, not proof of discrimination on its own") -- folded
            // into the existing DIR column below rather than adding a
            // 5th grid column to .table-row (index.css hardcodes 4).
            defaultRate:
              numberFrom(row, ["group_actual_default_rate"]) ?? undefined,
          },
        ]
      })
    if (raw && typeof raw === "object")
      return Object.entries(raw as ApiRecord).flatMap(([group, value]) =>
        typeof value === "number" ? [{ group, dir: value }] : [],
      )
    return []
  }, [data])
  return (
    <>
      <PageHeader
        eyebrow="Responsible AI"
        title="Fairness & Responsible AI"
        description="Review group-level outcomes and identify signals that warrant deeper, contextual investigation."
        action={
          <Button variant="secondary" onClick={load} disabled={loading}>
            <RefreshCw size={16} /> Refresh audit
          </Button>
        }
      />
      <div className="method-banner">
        <span>
          <Scale size={21} />
        </span>
        <div>
          <strong>Interpret with care</strong>
          <p>
            A DIR below 0.80 is a signal for investigation under the commonly
            referenced four-fifths rule—not automatic proof of discrimination.
          </p>
        </div>
      </div>
      {error && (
        <div className="error-banner">
          <CircleHelp size={18} />
          <div>
            <strong>Audit unavailable</strong>
            <p>{error}</p>
          </div>
        </div>
      )}
      {loading ? (
        <div className="panel-loader">
          <RefreshCw size={24} />
          <span>Running fairness analysis…</span>
        </div>
      ) : rows.length ? (
        <>
          <section className="chart-card fairness-chart">
            <div className="card-heading">
              <div>
                <h2>Disparate Impact Ratio comparison</h2>
                <p>Reference threshold at DIR = 0.80</p>
              </div>
              <span className="threshold-key">
                <i /> Review threshold
              </span>
            </div>
            <div className="dir-chart">
              <div className="threshold-line">
                <span>0.80</span>
              </div>
              {rows.map((row) => (
                <div className="dir-row" key={row.group}>
                  <span>{row.group.replaceAll("_", " ")}</span>
                  <i>
                    <b
                      className={row.dir < 0.8 ? "flagged" : ""}
                      style={{ width: `${Math.min(row.dir / 1.2, 1) * 100}%` }}
                    />
                  </i>
                  <strong>{row.dir.toFixed(2)}</strong>
                </div>
              ))}
            </div>
          </section>
          <section className="table-card">
            <div className="card-heading">
              <div>
                <h2>Group-level audit</h2>
                <p>Groups returned by the fairness analytics endpoint</p>
              </div>
            </div>
            <div className="data-table">
              <div className="table-row table-head">
                <span>Group</span>
                <span>DIR</span>
                <span>Sample size</span>
                <span>Status</span>
              </div>
              {rows.map((row) => (
                <div className="table-row" key={row.group}>
                  <strong>{row.group.replaceAll("_", " ")}</strong>
                  <span>
                    {row.dir.toFixed(3)}
                    {row.defaultRate !== undefined
                      ? ` (actual default ${(row.defaultRate * 100).toFixed(1)}%)`
                      : ""}
                  </span>
                  <span>{row.sample ?? "Not returned"}</span>
                  <span
                    className={cx("status-pill", row.dir < 0.8 && "flagged")}
                  >
                    {row.dir < 0.8 ? "Investigate" : "Above threshold"}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : (
        !error && (
          <EmptyState
            icon={Scale}
            title="No audit groups returned"
            text="The fairness endpoint did not return group-level DIR metrics for display."
          />
        )
      )}
      <details className="methodology">
        <summary>
          <span>
            <BookOpen size={18} /> Methodology & responsible interpretation
          </span>
          <ChevronDown size={18} />
        </summary>
        <div>
          <p>
            DIR compares a group's favourable outcome rate with a reference
            group's rate. It should be reviewed alongside sample sizes, outcome
            definitions, underlying default rates, missing data, and relevant
            operational context.
          </p>
          <p>
            Small groups can produce unstable ratios. A complete review should
            involve domain experts, data-quality checks, and assessment of
            whether the selected reference group and outcome are appropriate.
          </p>
        </div>
      </details>
    </>
  )
}

function ReportsPage() {
  const [id, setId] = useState("")
  const [record, setRecord] = useState<ApiRecord | null>(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState("")
  const [companies, setCompanies] = useState<ApiRecord[]>([])
  const [listLoading, setListLoading] = useState(false)

  // Live search: whenever the search box changes, wait 300ms after the
  // last keystroke (debounce), then ask the backend for matching
  // companies. An empty box lists the most recent companies.
  useEffect(() => {
    let cancelled = false
    const timer = setTimeout(async () => {
      setListLoading(true)
      try {
        const data = await api.listCompanies(id.trim())
        if (!cancelled)
          setCompanies(
            Array.isArray(data.companies) ? (data.companies as ApiRecord[]) : [],
          )
      } catch {
        if (!cancelled) setCompanies([])
      } finally {
        if (!cancelled) setListLoading(false)
      }
    }, 300)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [id])

  const loadCompany = async (companyId: string) => {
    setLoading(true)
    setMessage("")
    setRecord(null)
    try {
      setRecord(await api.company(companyId))
    } catch (reason) {
      setMessage(
        reason instanceof Error ? reason.message : "Company record not found.",
      )
    } finally {
      setLoading(false)
    }
  }
  // "Find assessment" button / Enter key: look up exactly what was typed.
  const find = (event: FormEvent) => {
    event.preventDefault()
    void loadCompany(id.trim())
  }
  // Clicking a list row: same as typing its ID and pressing "Find assessment".
  const selectCompany = (companyId: string) => {
    setId(companyId)
    void loadCompany(companyId)
  }
  const download = async () => {
    try {
      await api.downloadReport(id)
      setMessage("PDF report downloaded successfully.")
    } catch (reason) {
      setMessage(
        reason instanceof Error ? reason.message : "Report download failed.",
      )
    }
  }
  return (
    <>
      <PageHeader
        eyebrow="Reporting workspace"
        title="Reports & History"
        description="Search for a business by name or ID, select it, and download its credit report."
      />
      <form className="search-card" onSubmit={find}>
        <div>
          <Search size={20} />
          <input
            value={id}
            onChange={(event) => setId(event.target.value)}
            placeholder="Search by company name or ID"
            aria-label="Company name or ID"
          />
        </div>
        <Button disabled={!id || loading}>
          {loading ? "Searching…" : "Find assessment"}
        </Button>
      </form>
      <div className="company-list">
        {companies.map((company) => {
          const companyId = String(company.company_id ?? "")
          const band = valueFrom(company, ["latest_risk_band"])
          return (
            <button
              type="button"
              className="company-row"
              key={companyId}
              onClick={() => selectCompany(companyId)}
            >
              <strong>{valueFrom(company, ["company_name"]) || companyId}</strong>
              <small>{companyId}</small>
              {band ? (
                <span className={cx("risk-badge", band.toLowerCase().replace(" ", "-"))}>
                  <i /> {band}
                </span>
              ) : (
                <span />
              )}
            </button>
          )
        })}
        {!companies.length && (
          <div className="inline-note">
            {listLoading ? "Searching…" : "No companies match your search."}
          </div>
        )}
      </div>
      {message && <div className="inline-note">{message}</div>}
      {record ? (
        <section className="report-record">
          <div className="report-icon">
            <FileText size={24} />
          </div>
          <div>
            <span className="eyebrow">Company record</span>
            <h2>
              {valueFrom(record, ["company_name", "name"]) || `Business ${id}`}
            </h2>
            <div className="record-meta">
              <span>
                <small>Business ID</small>
                <strong>{valueFrom(record, ["company_id", "id"]) || id}</strong>
              </span>
              {/* backend/schemas.py's CompanyHistoryResponse has NO
                  top-level credit_score/risk_band/assessed_at -- those
                  only exist inside each entry of `assessments` (newest
                  first). Read the latest one instead of a non-existent
                  top-level field. */}
              <span>
                <small>Credit score</small>
                <strong>
                  {valueFrom(
                    (Array.isArray(record.assessments)
                      ? (record.assessments[0] as ApiRecord)
                      : null) || record,
                    ["credit_score", "score"],
                  ) || "Not returned"}
                </strong>
              </span>
              <span>
                <small>Risk category</small>
                <strong>
                  {valueFrom(
                    (Array.isArray(record.assessments)
                      ? (record.assessments[0] as ApiRecord)
                      : null) || record,
                    ["risk_band", "risk_category", "risk_classification"],
                  ) || "Not returned"}
                </strong>
              </span>
              <span>
                <small>Assessment date</small>
                <strong>
                  {valueFrom(
                    (Array.isArray(record.assessments)
                      ? (record.assessments[0] as ApiRecord)
                      : null) || record,
                    ["assessed_at", "assessment_date", "created_at"],
                  ) || "Not returned"}
                </strong>
              </span>
            </div>
          </div>
          <Button onClick={download}>
            <Download size={16} /> Download PDF
          </Button>
        </section>
      ) : (
        <EmptyState
          icon={FileClock}
          title="No assessment selected"
          text="Pick a company from the list above, or type a name or ID to narrow it down."
        />
      )}
    </>
  )
}

function SettingsPage({
  theme,
  setTheme,
}: {
  theme: "dark" | "light"
  setTheme: (value: "dark" | "light") => void
}) {
  return (
    <>
      <PageHeader
        eyebrow="Workspace preferences"
        title="Settings"
        description="Review connection details and personalise this browser's workspace."
      />
      <section className="form-card settings-card">
        <div className="card-title">
          <span>
            <Sun size={20} />
          </span>
          <div>
            <h2>Appearance</h2>
            <p>Choose the visual mode used in this browser.</p>
          </div>
        </div>
        <div className="theme-options">
          <button
            className={cx(theme === "dark" && "active")}
            onClick={() => setTheme("dark")}
          >
            <Moon size={20} />
            <strong>Midnight</strong>
            <small>Focused dark workspace</small>
          </button>
          <button
            className={cx(theme === "light" && "active")}
            onClick={() => setTheme("light")}
          >
            <Sun size={20} />
            <strong>Daylight</strong>
            <small>High-contrast light workspace</small>
          </button>
        </div>
      </section>
      <section className="form-card settings-card">
        <div className="card-title">
          <span>
            <Activity size={20} />
          </span>
          <div>
            <h2>API connection</h2>
            <p>
              Configured through VITE_API_URL (NEXT_PUBLIC_API_URL fallback).
            </p>
          </div>
        </div>
        <div className="api-value">
          <span>Base URL</span>
          <code>{api.baseUrl}</code>
        </div>
      </section>
    </>
  )
}

export default function App() {
  const [page, setPage] = useState<Page>("home")
  const [menuOpen, setMenuOpen] = useState(false)
  const [theme, setTheme] = useState<"dark" | "light">(() =>
    localStorage.getItem("msme-theme") === "light" ? "light" : "dark",
  )
  const [form, setForm] = useState<FormData>(() => {
    try {
      return {
        ...defaultForm,
        ...JSON.parse(localStorage.getItem("msme-assessment") || "{}"),
      }
    } catch {
      return defaultForm
    }
  })
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  const [portfolio, setPortfolio] = useState<ApiRecord | null>(null)
  const [portfolioLoading, setPortfolioLoading] = useState(true)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem("msme-theme", theme)
  }, [theme])
  useEffect(() => {
    api
      .health()
      .then(() => setBackendOnline(true))
      .catch(() => setBackendOnline(false))
    api
      .portfolio()
      .then(setPortfolio)
      .catch(() => setPortfolio(null))
      .finally(() => setPortfolioLoading(false))
  }, [])
  const goTo = (next: Page) => {
    setPage(next)
    setMenuOpen(false)
    window.scrollTo({ top: 0, behavior: "smooth" })
  }
  const update = <K extends keyof FormData>(key: K, value: FormData[K]) =>
    setForm((current) => ({ ...current, [key]: value }))
  const save = () => {
    localStorage.setItem("msme-assessment", JSON.stringify(form))
    setSaved(true)
    window.setTimeout(() => setSaved(false), 2400)
  }

  let content: ReactNode
  const props = { form, update, goTo, save }
  switch (page) {
    case "business":
      content = <BusinessPage {...props} />
      break
    case "banking":
      content = <BankingPage {...props} />
      break
    case "tax":
      content = <TaxPage {...props} />
      break
    case "evaluate":
      content = <EvaluatePage form={form} goTo={goTo} />
      break
    case "portfolio":
      content = <PortfolioPage />
      break
    case "fairness":
      content = <FairnessPage />
      break
    case "reports":
      content = <ReportsPage />
      break
    case "settings":
      content = <SettingsPage theme={theme} setTheme={setTheme} />
      break
    default:
      content = (
        <HomePage
          goTo={goTo}
          portfolio={portfolio}
          loading={portfolioLoading}
        />
      )
  }

  return (
    <div className="app-shell">
      <aside className={cx("sidebar", menuOpen && "open")}>
        <div className="brand">
          <span>
            <BarChart3 size={22} />
          </span>
          <div>
            <strong>MSME Credit AI</strong>
            <small>Alternative intelligence</small>
          </div>
          <button
            className="mobile-close"
            onClick={() => setMenuOpen(false)}
            aria-label="Close navigation"
          >
            <X size={20} />
          </button>
        </div>
        <nav>
          {navItems.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={cx(page === id && "active")}
              onClick={() => goTo(id)}
            >
              <Icon size={18} />
              <span>{label}</span>
              {id === "evaluate" && <i>AI</i>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="backend-status">
            <span
              className={
                backendOnline === true
                  ? "online"
                  : backendOnline === false
                    ? "offline"
                    : ""
              }
            >
              <i />
            </span>
            <div>
              <strong>
                {backendOnline === null
                  ? "Checking backend"
                  : backendOnline
                    ? "Backend connected"
                    : "Backend unavailable"}
              </strong>
              <small>
                {backendOnline
                  ? "API services operational"
                  : "Live data may be unavailable"}
              </small>
            </div>
          </div>
          <button
            className="theme-toggle"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            <span>
              {theme === "dark" ? <Moon size={16} /> : <Sun size={16} />}
            </span>
            <strong>{theme === "dark" ? "Dark mode" : "Light mode"}</strong>
            <i>
              <b />
            </i>
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <div className="mobile-bar">
          <button
            onClick={() => setMenuOpen(true)}
            aria-label="Open navigation"
          >
            <Menu size={21} />
          </button>
          <div className="brand">
            <span>
              <BarChart3 size={19} />
            </span>
            <strong>MSME Credit AI</strong>
          </div>
          <button aria-label="Notifications">
            <Bell size={19} />
          </button>
        </div>
        <main>{content}</main>
        <footer>
          <span>
            <ShieldCheck size={15} /> Educational prototype using synthetic
            data. Predictions are not validated for real lending decisions.
          </span>
          <span>Responsible AI · Explainable by design</span>
        </footer>
      </div>
      {menuOpen && (
        <button
          className="menu-backdrop"
          aria-label="Close navigation"
          onClick={() => setMenuOpen(false)}
        />
      )}
      {saved && (
        <div className="toast">
          <Check size={16} /> Progress saved in this browser.
        </div>
      )}
    </div>
  )
}
