import { useEffect, useState } from "react";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  Clock3,
  FileSpreadsheet,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  Plus,
  Trash2,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  Users,
  X,
  RefreshCw,
} from "lucide-react";

const API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const defaults = {
  quantity: 50,
  min_ram_gb: 16,
  min_ssd_gb: 512,
  max_price: 60000,
  max_delivery_days: 15,
  min_warranty_years: 3,
};

const money = (n) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(n || 0));

function App() {
  const [page, S] = useState("Overview");
  const [health, H] = useState("Checking");
  const [requirements, R] = useState(defaults);
  const [files, F] = useState([]);
  const [parsed, P] = useState(null);
  const [vendors, V] = useState([]);
  const [busy, B] = useState(false);
  const [msg, M] = useState("");
  const [run, Q] = useState(null);
  const [runId, I] = useState("");
  const [approval, A] = useState({
    approved: true,
    reviewer: "Procurement Manager",
    notes: "",
  });
  const [review, Rev] = useState(null);
  const [history, Hist] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [templateId, setTemplateId] = useState("chairs");
  const [constraints, setConstraints] = useState([]);
  const [dynamicVendors, setDynamicVendors] = useState([
    {
      name: "Vendor A",
      price: "2200",
      material: "steel",
      load_capacity_kg: "150",
      warranty_years: "2",
    },
    {
      name: "Vendor B",
      price: "2800",
      material: "plastic",
      load_capacity_kg: "100",
      warranty_years: "3",
    },
  ]);
  const [dynamicResults, setDynamicResults] = useState(null);

  async function check() {
    try {
      const r = await fetch(`${API}/health`);
      H(r.ok ? "Connected" : "Error");
    } catch {
      H("Offline");
    }
  }

  async function loadTemplates() {
    try {
      const response = await fetch(`${API}/templates`);
      const data = await response.json();

      if (!response.ok) {
        throw Error(data.detail || response.status);
      }

      const available = data.templates || [];
      setTemplates(available);

      if (available.length) {
        const preferred = available.some((item) => item.id === "chairs")
          ? "chairs"
          : available[0].id;

        const templateResponse = await fetch(`${API}/templates/${preferred}`);
        const templateData = await templateResponse.json();

        if (!templateResponse.ok) {
          throw Error(templateData.detail || templateResponse.status);
        }

        setTemplateId(preferred);
        setConstraints(templateData.constraints || []);
      }
    } catch (error) {
      M(`Template loading failed: ${error.message}`);
    }
  }

  async function chooseTemplate(id) {
    setTemplateId(id);
    setDynamicResults(null);

    try {
      const response = await fetch(`${API}/templates/${id}`);
      const data = await response.json();

      if (!response.ok) {
        throw Error(data.detail || response.status);
      }

      setConstraints(data.constraints || []);

      setDynamicVendors((old) =>
        old.map((vendor) => {
          const next = { ...vendor };

          (data.constraints || []).forEach((rule) => {
            if (!(rule.field in next)) {
              next[rule.field] = "";
            }
          });

          return next;
        }),
      );

      M(`Loaded ${data.name} template. You can edit or add constraints.`);
    } catch (error) {
      M(`Could not load template: ${error.message}`);
    }
  }

  function addConstraint() {
    setConstraints((old) => [
      ...old,
      {
        field: "",
        operator: ">=",
        value: "",
        severity: "mandatory",
      },
    ]);

    setDynamicResults(null);
  }

  function updateConstraint(index, key, value) {
    setConstraints((old) =>
      old.map((rule, i) => (i === index ? { ...rule, [key]: value } : rule)),
    );

    setDynamicResults(null);
  }

  function addDynamicVendor() {
    const vendor = {
      name: `Vendor ${String.fromCharCode(65 + dynamicVendors.length)}`,
    };

    constraints.forEach((rule) => {
      if (rule.field) {
        vendor[rule.field] = "";
      }
    });

    setDynamicVendors((old) => [...old, vendor]);
    setDynamicResults(null);
  }

  function updateDynamicVendor(index, field, value) {
    setDynamicVendors((old) =>
      old.map((vendor, i) =>
        i === index ? { ...vendor, [field]: value } : vendor,
      ),
    );

    setDynamicResults(null);
  }

  function toComparableValue(value, operator) {
    if (operator === "in") {
      if (Array.isArray(value)) {
        return value;
      }

      return String(value ?? "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
    }

    return toScalarValue(value);
  }

  function toScalarValue(value) {
    if (typeof value === "number") {
      return value;
    }

    const trimmed = String(value ?? "").trim();

    if (trimmed !== "" && Number.isFinite(Number(trimmed))) {
      return Number(trimmed);
    }

    return trimmed;
  }

  async function evaluateDynamic(e) {
    e.preventDefault();

    if (!constraints.length) {
      M("Add at least one constraint.");
      return;
    }

    if (!dynamicVendors.length) {
      M("Add at least one vendor to evaluate.");
      return;
    }

    const invalidRule = constraints.find(
      (rule) =>
        !String(rule.field || "").trim() ||
        rule.value === "" ||
        rule.value == null,
    );

    if (invalidRule) {
      M("Every constraint needs a field and value.");
      return;
    }

    B(true);
    M("");

    try {
      const payload = {
        constraints: constraints.map((rule) => ({
          ...rule,
          field: rule.field.trim(),
          value: toComparableValue(rule.value, rule.operator),
        })),

        vendors: dynamicVendors.map((vendor, index) => {
          const cleaned = {
            name: vendor.name || `Vendor ${index + 1}`,
          };

          constraints.forEach((rule) => {
            const field = String(rule.field || "").trim();

            if (!field) {
              return;
            }

            const raw = vendor[field];

            if (raw === "" || raw == null) {
              return;
            }

            cleaned[field] = toScalarValue(raw);
          });

          return cleaned;
        }),
      };

      const response = await fetch(`${API}/evaluate-dynamic`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        const detail = data.detail;

        throw Error(
          typeof detail === "string"
            ? detail
            : detail?.errors?.join(" ") ||
                JSON.stringify(detail) ||
                response.status,
        );
      }

      setDynamicResults(data);
      M("Dynamic constraint evaluation completed.");
    } catch (error) {
      M(`Dynamic evaluation failed: ${error.message}`);
    } finally {
      B(false);
    }
  }

  function buildDynamicPayload() {
    return {
      constraints: constraints.map((rule) => ({
        ...rule,
        field: rule.field.trim(),
        value: toComparableValue(rule.value, rule.operator),
      })),

      vendors: dynamicVendors.map((vendor, index) => {
        const cleaned = {
          name: vendor.name || `Vendor ${index + 1}`,
        };

        // Price is always sent: the ranking uses it even without a price rule.
        if (vendor.price !== "" && vendor.price != null) {
          cleaned.price = toScalarValue(vendor.price);
        }

        constraints.forEach((rule) => {
          const field = String(rule.field || "").trim();

          if (!field) {
            return;
          }

          const raw = vendor[field];

          if (raw === "" || raw == null) {
            return;
          }

          cleaned[field] = toScalarValue(raw);
        });

        return cleaned;
      }),
    };
  }

  function errorText(data, status) {
    const detail = data?.detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || JSON.stringify(item)).join(" ");
    }

    return detail?.errors?.join(" ") || JSON.stringify(detail) || status;
  }

  async function runDynamicWorkflow() {
    if (!constraints.length || !dynamicVendors.length) {
      M("Add at least one constraint and one vendor.");
      return;
    }

    const invalidRule = constraints.find(
      (rule) =>
        !String(rule.field || "").trim() ||
        rule.value === "" ||
        rule.value == null,
    );

    if (invalidRule) {
      M("Every constraint needs a field and value.");
      return;
    }

    B(true);
    M("");

    try {
      const r = await fetch(`${API}/runs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(buildDynamicPayload()),
      });

      const d = await r.json();

      if (!r.ok) {
        throw Error(errorText(d, r.status));
      }

      Q(d);
      I(d.run_id);

      Hist((old) => [{ ...d, date: new Date().toLocaleString() }, ...old]);

      S("Results");
    } catch (error) {
      M(`Workflow failed: ${error.message}`);
    } finally {
      B(false);
    }
  }

  useEffect(() => {
    check();
    loadTemplates();
  }, []);

  async function upload(e) {
    e.preventDefault();

    if (!files.length) {
      M("Choose quotation files first.");
      return;
    }

    B(true);
    M("");

    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));

    try {
      const r = await fetch(`${API}/upload-quotations`, {
        method: "POST",
        body: fd,
      });

      const d = await r.json();

      if (!r.ok) {
        throw Error(d.detail || r.status);
      }

      P(d);
      M("Quotation parsing completed. Review the extracted records below.");
    } catch (e) {
      M(`Upload failed: ${e.message}. Check backend/CORS.`);
    } finally {
      B(false);
    }
  }

  const records =
    parsed?.files?.flatMap((f) =>
      (f.vendors || []).map((v) => ({
        ...v,
        source_file: f.source_file,
      })),
    ) || [];

  function load() {
    const good = records.filter((v) => v.complete && !v.missing_fields?.length);

    V(
      good.map(
        ({ name, price, ram_gb, ssd_gb, delivery_days, warranty_years }) => ({
          name,
          price,
          ram_gb,
          ssd_gb,
          delivery_days,
          warranty_years,
        }),
      ),
    );

    S("New analysis");

    M(
      good.length
        ? `${good.length} complete vendor(s) loaded.`
        : "No complete vendor records. Check missing fields.",
    );
  }

  async function analyze(e) {
    e.preventDefault();

    if (!vendors.length) {
      M("Add vendors by uploading a quotation first.");
      return;
    }

    B(true);
    M("");

    try {
      const r = await fetch(`${API}/runs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          requirements,
          vendors,
        }),
      });

      const d = await r.json();

      if (!r.ok) {
        throw Error(d.detail || r.status);
      }

      Q(d);
      I(d.run_id);

      Hist((old) => [{ ...d, date: new Date().toLocaleString() }, ...old]);

      S("Results");
    } catch (e) {
      M(`Analysis failed: ${e.message}`);
    } finally {
      B(false);
    }
  }
  async function submit(e) {
    e.preventDefault();
    B(true);

    try {
      const r = await fetch(`${API}/runs/${runId}/approval`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(approval),
      });

      const d = await r.json();

      if (!r.ok) {
        throw Error(d.detail || r.status);
      }

      Rev(d);
      Q((old) => ({ ...old, ...d }));

      Hist((old) =>
        old.map((x) => (x.run_id === runId ? { ...x, status: d.status } : x)),
      );

      M("Review saved.");
    } catch (e) {
      Rev({ error: e.message });
    } finally {
      B(false);
    }
  }

  const rows = run?.ranked_vendors || run?.evaluation_results || [];

  const nav = [
    ["Overview", LayoutDashboard],
    ["Quotations", FileSpreadsheet],
    ["New analysis", Sparkles],
    ["Results", Activity],
    ["Approvals", ShieldCheck],
  ];

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo">
            <Sparkles />
          </span>
          <div>
            <b>
              PROCURE<span>.AI</span>
            </b>
            <small>INTELLIGENT SOURCING</small>
          </div>
        </div>

        <div className="workspace">
          P
          <div>
            <b>Procurement team</b>
            <small>Workspace</small>
          </div>
        </div>

        <label className="navlabel">WORKSPACE</label>

        {nav.map(([n, Icon]) => (
          <button
            key={n}
            className={`nav ${page === n ? "active" : ""}`}
            onClick={() => S(n)}
          >
            <Icon size={17} />
            {n}
          </button>
        ))}

        <div className="sidebottom">
          <ShieldCheck />
          <b>Transparent procurement</b>
          <p>
            Rules-first evaluation with human approval and auditable decisions.
          </p>
        </div>
      </aside>

      <main>
        <header>
          <button
            className="mobile"
            onClick={() =>
              document.querySelector(".sidebar")?.classList.toggle("show")
            }
          >
            <Menu />
          </button>

          <div>
            <h2>{page}</h2>
            <p>AI-powered procurement workspace</p>
          </div>

          <div className="health">
            <span className={`dot ${health === "Connected" ? "online" : ""}`} />
            API: {health}
            <button onClick={check} title="Refresh connection">
              <RefreshCw size={15} />
            </button>
          </div>
        </header>

        {msg && (
          <div className="notice">
            <span>{msg}</span>
            <button onClick={() => M("")}>
              <X size={16} />
            </button>
          </div>
        )}

        {page === "Overview" && (
          <section className="content">
            <div className="hero">
              <div>
                <span className="eyebrow">PROCUREMENT INTELLIGENCE</span>
                <h1>Better decisions. Clearer procurement.</h1>
                <p>
                  Compare supplier quotations, apply procurement rules, and keep
                  human approval in control.
                </p>
                <button className="primary" onClick={() => S("New analysis")}>
                  Start an analysis <ArrowRight size={16} />
                </button>
              </div>
              <div className="heroicon">
                <Sparkles size={64} />
              </div>
            </div>

            <div className="stats">
              <div className="stat">
                <span>API status</span>
                <b>{health}</b>
                <small>Backend connection</small>
              </div>
              <div className="stat">
                <span>Local sessions</span>
                <b>{history.length}</b>
                <small>Analyses in this session</small>
              </div>
              <div className="stat">
                <span>Vendors loaded</span>
                <b>{vendors.length}</b>
                <small>Current analysis</small>
              </div>
              <div className="stat">
                <span>Dynamic rules</span>
                <b>{constraints.length}</b>
                <small>Editable constraints</small>
              </div>
            </div>

            <div className="grid2">
              <div className="panel">
                <div className="panelhead">
                  <div>
                    <h3>Quick actions</h3>
                    <p>Continue your procurement workflow</p>
                  </div>
                </div>

                <button className="actionrow" onClick={() => S("Quotations")}>
                  <FileSpreadsheet />
                  <span>
                    <b>Upload quotations</b>
                    <small>Extract supplier details from files</small>
                  </span>
                  <ArrowRight />
                </button>

                <button className="actionrow" onClick={() => S("New analysis")}>
                  <Sparkles />
                  <span>
                    <b>New analysis</b>
                    <small>Set rules and evaluate suppliers</small>
                  </span>
                  <ArrowRight />
                </button>

                <button className="actionrow" onClick={() => S("Approvals")}>
                  <ShieldCheck />
                  <span>
                    <b>Review decisions</b>
                    <small>Approve or reject a recommendation</small>
                  </span>
                  <ArrowRight />
                </button>
              </div>

              <div className="panel">
                <div className="panelhead">
                  <div>
                    <h3>How it works</h3>
                    <p>Rules-first, human-controlled workflow</p>
                  </div>
                </div>

                <div className="steps">
                  <div>
                    <span>1</span> Upload quotations
                  </div>
                  <div>
                    <span>2</span> Apply mandatory and preferred rules
                  </div>
                  <div>
                    <span>3</span> Compare eligible vendors
                  </div>
                  <div>
                    <span>4</span> Record human approval
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}
        {page === "New analysis" && (
          <>
            <div className="heading">
              <div>
                <label>PROCUREMENT WORKFLOW</label>
                <h1>New procurement analysis</h1>
                <p>
                  Configure requirements, compare vendors, and evaluate
                  procurement rules.
                </p>
              </div>
            </div>
            <section className="panel" style={{ marginBottom: 20 }}>
              <div className="panelhead">
                <div>
                  <h2>Dynamic procurement builder</h2>
                  <p>
                    Choose a template, add custom constraints, and evaluate
                    suppliers.
                  </p>
                </div>
                <span className="tag green">Custom rules</span>
              </div>

              <form onSubmit={evaluateDynamic}>
                <div className="fields" style={{ marginBottom: 18 }}>
                  <label>
                    Product template
                    <select
                      value={templateId}
                      onChange={(e) => chooseTemplate(e.target.value)}
                    >
                      {templates.map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.name}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <div style={{ display: "grid", gap: 12 }}>
                  {constraints.map((rule, index) => (
                    <div
                      key={`${index}-${rule.field}`}
                      style={{
                        border: "1px solid var(--border, #e5e7eb)",
                        borderRadius: 12,
                        padding: 14,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: 10,
                          marginBottom: 10,
                        }}
                      >
                        <b>Constraint {index + 1}</b>

                        <button
                          type="button"
                          className="secondary"
                          onClick={() => {
                            setConstraints((old) =>
                              old.filter((_, i) => i !== index),
                            );
                            setDynamicResults(null);
                          }}
                        >
                          <Trash2 size={15} /> Remove
                        </button>
                      </div>

                      <div className="fields">
                        <label>
                          Field name
                          <input
                            value={rule.field}
                            placeholder="e.g. load_capacity_kg"
                            onChange={(e) =>
                              updateConstraint(index, "field", e.target.value)
                            }
                            required
                          />
                        </label>

                        <label>
                          Operator
                          <select
                            value={rule.operator}
                            onChange={(e) =>
                              updateConstraint(
                                index,
                                "operator",
                                e.target.value,
                              )
                            }
                          >
                            <option value=">=">≥ Greater than or equal</option>
                            <option value="<=">≤ Less than or equal</option>
                            <option value=">">Greater than</option>
                            <option value="<">Less than</option>
                            <option value="=">= Equal</option>
                            <option value="!=">≠ Not equal</option>
                            <option value="in">in Allowed values</option>
                          </select>
                        </label>

                        <label>
                          Value{" "}
                          {rule.operator === "in" ? "(comma-separated)" : ""}
                          <input
                            value={
                              Array.isArray(rule.value)
                                ? rule.value.join(", ")
                                : (rule.value ?? "")
                            }
                            placeholder={
                              rule.operator === "in"
                                ? "steel, metal"
                                : "Enter requirement"
                            }
                            onChange={(e) =>
                              updateConstraint(index, "value", e.target.value)
                            }
                            required
                          />
                        </label>

                        <label>
                          Severity
                          <select
                            value={rule.severity}
                            onChange={(e) =>
                              updateConstraint(
                                index,
                                "severity",
                                e.target.value,
                              )
                            }
                          >
                            <option value="mandatory">Mandatory</option>
                            <option value="preferred">Preferred</option>
                          </select>
                        </label>
                      </div>
                    </div>
                  ))}
                </div>

                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 10,
                    margin: "16px 0",
                  }}
                >
                  <button
                    type="button"
                    className="secondary"
                    onClick={addConstraint}
                  >
                    <Plus size={16} /> Add Custom Constraint
                  </button>

                  <button
                    type="button"
                    className="secondary"
                    onClick={addDynamicVendor}
                  >
                    <Plus size={16} /> Add Vendor
                  </button>
                </div>

                <h3 style={{ marginBottom: 8 }}>Vendor data</h3>
                <p className="sub">
                  Enter values for the fields used by your constraints. Leave
                  unknown values blank; they will be marked Needs Review.
                </p>

                <div
                  style={{
                    display: "grid",
                    gap: 12,
                    marginTop: 12,
                  }}
                >
                  {dynamicVendors.map((vendor, index) => (
                    <div
                      key={index}
                      style={{
                        border: "1px solid var(--border, #e5e7eb)",
                        borderRadius: 12,
                        padding: 14,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          gap: 10,
                          alignItems: "center",
                          marginBottom: 10,
                        }}
                      >
                        <label style={{ flex: 1 }}>
                          Vendor name
                          <input
                            value={vendor.name || ""}
                            onChange={(e) =>
                              updateDynamicVendor(index, "name", e.target.value)
                            }
                            required
                          />
                        </label>

                        <button
                          type="button"
                          className="secondary"
                          onClick={() => {
                            setDynamicVendors((old) =>
                              old.filter((_, i) => i !== index),
                            );
                            setDynamicResults(null);
                          }}
                        >
                          <Trash2 size={15} /> Remove
                        </button>
                      </div>

                      <div className="fields">
                        {[
                          ...new Set(
                            constraints
                              .map((item) => item.field.trim())
                              .filter(Boolean),
                          ),
                        ].map((field) => (
                          <label key={field}>
                            {field}
                            <input
                              value={vendor[field] ?? ""}
                              placeholder="Leave blank if unknown"
                              onChange={(e) =>
                                updateDynamicVendor(
                                  index,
                                  field,
                                  e.target.value,
                                )
                              }
                            />
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                <button
                  className="primary"
                  type="submit"
                  disabled={
                    busy || !constraints.length || !dynamicVendors.length
                  }
                  style={{ marginTop: 18 }}
                >
                  {busy ? (
                    <LoaderCircle className="spin" />
                  ) : (
                    <Sparkles size={16} />
                  )}
                  Evaluate dynamic constraints
                </button>
              </form>

              {dynamicResults && (
                <div style={{ marginTop: 22 }}>
                  <div className="panelhead">
                    <div>
                      <h2>Dynamic evaluation results</h2>
                      <p>
                        {dynamicResults.vendors_evaluated} vendor(s) evaluated
                      </p>
                    </div>
                  </div>

                  <div style={{ display: "grid", gap: 12 }}>
                    {dynamicResults.results.map((result, index) => (
                      <div
                        key={`${result.vendor?.name || "vendor"}-${index}`}
                        style={{
                          border: "1px solid var(--border, #e5e7eb)",
                          borderRadius: 12,
                          padding: 14,
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            alignItems: "center",
                            justifyContent: "space-between",
                            gap: 10,
                          }}
                        >
                          <b>{result.vendor?.name || `Vendor ${index + 1}`}</b>

                          <span
                            className={`tag ${
                              result.status === "eligible"
                                ? "green"
                                : result.status === "needs_review"
                                  ? "amber"
                                  : "red"
                            }`}
                          >
                            {result.status.replaceAll("_", " ")}
                          </span>
                        </div>

                        {result.mandatory_failures?.length > 0 && (
                          <p className="warning">
                            Mandatory failures:{" "}
                            {result.mandatory_failures
                              .map(
                                (item) =>
                                  `${item.field} ${item.operator} ${String(
                                    item.expected,
                                  )} (actual: ${String(item.actual)})`,
                              )
                              .join("; ")}
                          </p>
                        )}

                        {result.preferred_misses?.length > 0 && (
                          <p className="sub">
                            Preferred misses:{" "}
                            {result.preferred_misses
                              .map(
                                (item) =>
                                  `${item.field} ${item.operator} ${String(
                                    item.expected,
                                  )}`,
                              )
                              .join("; ")}
                          </p>
                        )}

                        {result.missing_fields?.length > 0 && (
                          <p className="warning">
                            Needs data: {result.missing_fields.join(", ")}
                          </p>
                        )}

                        {result.errors?.length > 0 && (
                          <p className="warning">{result.errors.join("; ")}</p>
                        )}
                      </div>
                    ))}
                  </div>

                  <button
                    className="primary"
                    type="button"
                    disabled={busy}
                    onClick={runDynamicWorkflow}
                    style={{ marginTop: 16 }}
                  >
                    Start approval workflow <ArrowRight size={16} />
                  </button>
                </div>
              )}
            </section>{" "}
            <form className="analysis panel" onSubmit={analyze}>
              <div className="panelhead">
                <div>
                  <h2>Standard procurement analysis</h2>
                  <p>
                    Compare laptop quotations using the existing procurement
                    workflow.
                  </p>
                </div>
              </div>

              <div className="fields">
                {Object.entries(requirements).map(([key, value]) => (
                  <label key={key}>
                    {key.replaceAll("_", " ")}
                    <input
                      type="number"
                      min="0"
                      value={value}
                      onChange={(e) =>
                        R((old) => ({
                          ...old,
                          [key]: Number(e.target.value),
                        }))
                      }
                      required
                    />
                  </label>
                ))}
              </div>

              <div style={{ marginTop: 16 }}>
                <h3>Vendors loaded from quotations</h3>
                <p className="sub">
                  Upload quotations first, then load complete vendor records.
                </p>

                <div className="stats">
                  <div className="stat">
                    <span>Loaded vendors</span>
                    <b>{vendors.length}</b>
                  </div>
                </div>

                {vendors.length > 0 && (
                  <div style={{ overflowX: "auto" }}>
                    <table>
                      <thead>
                        <tr>
                          <th>Vendor</th>
                          <th>Price</th>
                          <th>RAM</th>
                          <th>SSD</th>
                          <th>Delivery days</th>
                          <th>Warranty</th>
                        </tr>
                      </thead>
                      <tbody>
                        {vendors.map((vendor, index) => (
                          <tr key={`${vendor.name}-${index}`}>
                            <td>{vendor.name}</td>
                            <td>{money(vendor.price)}</td>
                            <td>{vendor.ram_gb} GB</td>
                            <td>{vendor.ssd_gb} GB</td>
                            <td>{vendor.delivery_days}</td>
                            <td>{vendor.warranty_years} years</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <button
                  className="primary"
                  type="submit"
                  disabled={busy || vendors.length === 0}
                  style={{ marginTop: 16 }}
                >
                  {busy ? <LoaderCircle size={16} /> : <Sparkles size={16} />}
                  Run standard analysis
                </button>
              </div>
            </form>
          </>
        )}

        {page === "Quotations" && (
          <section className="content">
            <div className="heading">
              <div>
                <label>DOCUMENT PROCESSING</label>
                <h1>Supplier quotations</h1>
                <p>Upload quotation files and inspect extracted vendor data.</p>
              </div>
            </div>

            <form className="panel" onSubmit={upload}>
              <div className="panelhead">
                <div>
                  <h2>Upload files</h2>
                  <p>Choose one or more supported quotation documents.</p>
                </div>
                <UploadCloud size={24} />
              </div>

              <label className="uploadbox">
                <UploadCloud size={32} />
                <b>Choose quotation files</b>
                <span>PDF, Excel, CSV and supported document formats</span>
                <input
                  type="file"
                  multiple
                  accept=".pdf,.xlsx,.xls,.csv,.docx,.txt,.eml,.json"
                  onChange={(e) => F(Array.from(e.target.files || []))}
                />
              </label>

              {files.length > 0 && (
                <div style={{ marginTop: 14 }}>
                  {files.map((file, index) => (
                    <div key={`${file.name}-${index}`} className="actionrow">
                      <FileSpreadsheet />
                      <span>
                        <b>{file.name}</b>
                        <small>{(file.size / 1024).toFixed(1)} KB</small>
                      </span>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() =>
                          F((old) => old.filter((_, i) => i !== index))
                        }
                      >
                        <X size={15} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <button
                className="primary"
                type="submit"
                disabled={busy || files.length === 0}
                style={{ marginTop: 16 }}
              >
                {busy ? <LoaderCircle size={16} /> : <UploadCloud size={16} />}
                Upload and parse
              </button>
            </form>

            {parsed && (
              <div className="panel" style={{ marginTop: 20 }}>
                <div className="panelhead">
                  <div>
                    <h2>Extraction results</h2>
                    <p>Review the records returned by the backend.</p>
                  </div>
                  <span className="tag green">{records.length} record(s)</span>
                </div>

                {records.length > 0 ? (
                  <div style={{ overflowX: "auto" }}>
                    <table>
                      <thead>
                        <tr>
                          <th>Vendor</th>
                          <th>Price</th>
                          <th>RAM</th>
                          <th>SSD</th>
                          <th>Missing fields</th>
                        </tr>
                      </thead>
                      <tbody>
                        {records.map((record, index) => (
                          <tr key={`${record.name}-${index}`}>
                            <td>{record.name || "Unknown"}</td>
                            <td>
                              {record.price != null
                                ? money(record.price)
                                : "Unknown"}
                            </td>
                            <td>{record.ram_gb ?? "Unknown"}</td>
                            <td>{record.ssd_gb ?? "Unknown"}</td>
                            <td>
                              {record.missing_fields?.join(", ") || "None"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="sub">
                    No vendor records were returned. Check the upload response.
                  </p>
                )}

                <button
                  className="primary"
                  type="button"
                  onClick={load}
                  disabled={
                    !records.some(
                      (record) =>
                        record.complete && !record.missing_fields?.length,
                    )
                  }
                  style={{ marginTop: 16 }}
                >
                  Load complete vendors into analysis
                </button>
              </div>
            )}
          </section>
        )}

        {page === "Results" && (
          <section className="content">
            <div className="heading">
              <div>
                <label>ANALYSIS</label>
                <h1>Procurement results</h1>
                <p>Review the latest analysis and vendor recommendations.</p>
              </div>
            </div>

            {run ? (
              <div className="panel">
                <div className="panelhead">
                  <div>
                    <h2>Analysis summary</h2>
                    <p>Run ID: {runId || run.run_id || "Not available"}</p>
                  </div>
                  <span className="tag green">{run.status || "Completed"}</span>
                </div>

                {rows.length > 0 ? (
                  <div style={{ overflowX: "auto" }}>
                    <table>
                      <thead>
                        <tr>
                          <th>Rank</th>
                          <th>Vendor</th>
                          <th>Price</th>
                          <th>Status</th>
                          <th>Details</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((item, index) => {
                          const name =
                            typeof item.vendor === "string"
                              ? item.vendor
                              : item.vendor?.name ||
                                item.name ||
                                "Unknown vendor";
                          const price = item.price ?? item.vendor?.price;
                          const details = [
                            ...(item.reasons || item.failures || []),
                            ...(item.preferred_misses || []).map(
                              (miss) =>
                                `Preferred: ${miss.field} ${miss.operator} ${String(
                                  miss.expected,
                                )}`,
                            ),
                          ];

                          return (
                            <tr key={`${name}-${index}`}>
                              <td>{item.rank ?? "—"}</td>
                              <td>{name}</td>
                              <td>{price != null ? money(price) : "—"}</td>
                              <td>
                                {item.status || item.eligibility || "Evaluated"}
                              </td>
                              <td>
                                {details.length
                                  ? details.join("; ")
                                  : item.recommendation_reason || "—"}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <pre
                    style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}
                  >
                    {JSON.stringify(run, null, 2)}
                  </pre>
                )}

                {run.ai_explanations && (
                  <div style={{ marginTop: 18 }}>
                    <h3>AI explanation</h3>
                    {run.ai_explanations.summary && (
                      <p>{run.ai_explanations.summary}</p>
                    )}
                    {run.ai_explanations.selected_vendor_reason && (
                      <p>
                        <b>Why this vendor:</b>{" "}
                        {run.ai_explanations.selected_vendor_reason}
                      </p>
                    )}
                  </div>
                )}

                {run.ai_warnings?.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <h3>Warnings</h3>
                    {run.ai_warnings.map((warning, index) => (
                      <p key={index} className="warning">
                        {warning}
                      </p>
                    ))}
                  </div>
                )}

                <button
                  className="primary"
                  onClick={() => S("Approvals")}
                  style={{ marginTop: 16 }}
                >
                  Go to approval review <ArrowRight size={16} />
                </button>
              </div>
            ) : (
              <div className="panel">
                <Activity size={30} />
                <h2>No analysis yet</h2>
                <p>Run an analysis to see the results here.</p>
                <button className="primary" onClick={() => S("New analysis")}>
                  Start analysis
                </button>
              </div>
            )}

            {history.length > 0 && (
              <div className="panel" style={{ marginTop: 20 }}>
                <h2>Session history</h2>
                {history.map((item, index) => (
                  <div key={`${item.run_id}-${index}`} className="actionrow">
                    <Clock3 />
                    <span>
                      <b>{item.run_id || `Analysis ${index + 1}`}</b>
                      <small>
                        {item.date || item.status || "Saved session"}
                      </small>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {page === "Approvals" && (
          <section className="content">
            <div className="heading">
              <div>
                <label>HUMAN-IN-THE-LOOP</label>
                <h1>Approval review</h1>
                <p>Record a procurement manager's approval decision.</p>
              </div>
            </div>

            {runId ? (
              <form className="panel" onSubmit={submit}>
                <div className="panelhead">
                  <div>
                    <h2>Review analysis</h2>
                    <p>Run ID: {runId}</p>
                  </div>
                  <ShieldCheck size={25} />
                </div>

                <div className="fields">
                  <label>
                    Reviewer
                    <input
                      value={approval.reviewer}
                      onChange={(e) =>
                        A((old) => ({
                          ...old,
                          reviewer: e.target.value,
                        }))
                      }
                      required
                    />
                  </label>

                  <label>
                    Decision
                    <select
                      value={approval.approved ? "approve" : "reject"}
                      onChange={(e) =>
                        A((old) => ({
                          ...old,
                          approved: e.target.value === "approve",
                        }))
                      }
                    >
                      <option value="approve">Approve</option>
                      <option value="reject">Reject</option>
                    </select>
                  </label>
                </div>

                <label style={{ display: "block", marginTop: 16 }}>
                  Review notes
                  <textarea
                    rows={4}
                    value={approval.notes}
                    placeholder="Explain the reason for your decision..."
                    onChange={(e) =>
                      A((old) => ({
                        ...old,
                        notes: e.target.value,
                      }))
                    }
                  />
                </label>

                <button
                  className="primary"
                  type="submit"
                  disabled={busy}
                  style={{ marginTop: 16 }}
                >
                  {busy ? (
                    <LoaderCircle size={16} />
                  ) : (
                    <CheckCircle2 size={16} />
                  )}
                  Submit decision
                </button>

                {review && (
                  <div className="notice" style={{ marginTop: 16 }}>
                    {review.error
                      ? `Review error: ${review.error}`
                      : `Review response: ${JSON.stringify(review)}`}
                  </div>
                )}
              </form>
            ) : (
              <div className="panel">
                <ShieldCheck size={30} />
                <h2>No run selected</h2>
                <p>
                  Complete a standard procurement analysis first. Its run ID
                  will be available here for review.
                </p>
                <button className="primary" onClick={() => S("New analysis")}>
                  Start analysis
                </button>
              </div>
            )}
          </section>
        )}

        <footer>
          <span>PROCURE.AI</span>
          <span>Rules-first procurement · Human-controlled decisions</span>
        </footer>
      </main>
    </div>
  );
}

export default App;
