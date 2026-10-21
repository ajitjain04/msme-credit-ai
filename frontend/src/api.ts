const API_BASE_URL = (
  import.meta.env.VITE_API_URL ||
  import.meta.env.NEXT_PUBLIC_API_URL ||
  ""
).replace(/\/$/, "")

type JsonRecord = Record<string, unknown>

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    // A multipart upload (FormData) must NOT get a JSON Content-Type: the
    // browser sets multipart/form-data plus its boundary string itself.
    headers:
      options?.body instanceof FormData
        ? options.headers
        : {
            "Content-Type": "application/json",
            ...options?.headers,
          },
  })

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`
    try {
      const body = (await response.json()) as JsonRecord
      if (Array.isArray(body.detail)) {
        // FastAPI/Pydantic validation errors (422) return `detail` as a
        // LIST of {loc, msg, type} objects, not a string -- String() on
        // that array would show "[object Object]". Flatten it into one
        // readable line instead.
        detail = body.detail
          .map((item) => {
            const row = item as JsonRecord
            const loc = Array.isArray(row.loc) ? row.loc.join(".") : ""
            return row.msg ? `${loc ? `${loc}: ` : ""}${row.msg}` : JSON.stringify(row)
          })
          .join("; ")
      } else {
        detail = String(body.detail || body.message || detail)
      }
    } catch {
      // Keep the HTTP status message when the backend does not return JSON.
    }
    throw new Error(detail)
  }

  return response.json() as Promise<T>
}

export const api = {
  baseUrl: API_BASE_URL || "Same-origin API",
  health: () => request<JsonRecord>("/health"),
  evaluate: (payload: JsonRecord) =>
    request<JsonRecord>("/api/v1/evaluate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  portfolio: () => request<JsonRecord>("/api/v1/analytics/portfolio"),
  fairness: () => request<JsonRecord>("/api/v1/analytics/fairness"),
  company: (companyId: string) =>
    request<JsonRecord>(`/api/v1/company/${encodeURIComponent(companyId)}`),
  // POST /api/v1/parse-bank-statement (multipart) -> the 5 parsed banking fields
  parseBankStatement: (file: File) => {
    const body = new FormData()
    body.append("file", file)
    return request<JsonRecord>("/api/v1/parse-bank-statement", {
      method: "POST",
      body,
    })
  },
  // GET /api/v1/companies?q=... -> { companies: [...], count }
  listCompanies: (q?: string) =>
    request<JsonRecord>(
      `/api/v1/companies${q ? `?q=${encodeURIComponent(q)}` : ""}`,
    ),
  downloadReport: async (companyId: string) => {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/company/${encodeURIComponent(companyId)}/report/pdf`,
    )
    if (!response.ok) {
      throw new Error(`Report download failed with status ${response.status}`)
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `MSME-Credit-Assessment-${companyId}.pdf`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  },
}
