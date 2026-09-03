import type {
  AccessControlWorkbench,
  AnalyzerReport,
  AnalyzerSummary,
  ApiMap,
  AuthFlow,
  AskCopilotPayload,
  AskCopilotResponse,
  Asset,
  CreateInvestigationPayload,
  DiffResult,
  EvidenceAnnotation,
  EvidenceAttachment,
  EvidencePackage,
  EvidenceBundleVerification,
  Explanation,
  HttpTransaction,
  HuntHistory,
  IdentityProfile,
  Investigation,
  InvestigationStatus,
  JsFile,
  NextBestAction,
  ParameterInventory,
  Project,
  ProjectDetail,
  Readiness,
  ReconJob,
  ReconToolReference,
  Report,
  PracticeLab,
  PracticeResponse,
  ScopeAuditLogEntry,
  ScopeCheckResponse,
  SkillMap,
  AuthUser,
  AuthEvent,
  AuthSession,
  DiscoveredEndpoint,
  CrawlRejection,
  PublicMetadataDocument,
  AccessControlScenario,
  AccessControlMatrix,
} from "../types";

const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const csrf = document.cookie.split("; ").find((row) => row.startsWith("vajra_csrf="))?.split("=").slice(1).join("=");
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {}),
      ...(options?.headers ?? {}),
    },
  });
  if (res.status === 401 && !path.startsWith("/auth/login")) {
    window.dispatchEvent(new Event("vajra:unauthorized"));
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore body parse failure
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// Separate from request(): a FormData body must NOT get an explicit
// Content-Type - the browser sets its own multipart boundary. request()
// always forces application/json, which would corrupt the upload.
async function uploadFile<T>(path: string, formData: FormData, method: "POST" | "PUT" = "POST"): Promise<T> {
  const csrf = document.cookie.split("; ").find((row) => row.startsWith("vajra_csrf="))?.split("=").slice(1).join("=");
  const res = await fetch(`${BASE}${path}`, {
    method, body: formData, credentials: "same-origin",
    headers: csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {},
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore body parse failure
    }
    throw new Error(detail);
  }
  return res.json();
}

async function downloadFile(path: string, fallbackFilename: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { credentials: "same-origin" });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore body parse failure
    }
    throw new Error(detail);
  }
  const disposition = res.headers.get("content-disposition") ?? "";
  const encoded = disposition.match(/filename\*=utf-8''([^;]+)/i)?.[1];
  const quoted = disposition.match(/filename="([^"]+)"/i)?.[1];
  const filename = encoded ? decodeURIComponent(encoded) : quoted || fallbackFilename;
  const objectUrl = URL.createObjectURL(await res.blob());
  try {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

async function practiceRequest(path: string, headers: Record<string, string> = {}): Promise<PracticeResponse> {
  const res = await fetch(`${BASE}${path}`, { headers });
  return {
    status: res.status,
    statusText: res.statusText,
    headers: Object.fromEntries(res.headers.entries()),
    body: await res.text(),
  };
}

export interface CreateProjectPayload {
  name: string;
  target: string;
  allowed_domains: string[];
  allowed_subdomains: string[];
  excluded_assets: string[];
  program_rules: string;
  testing_restrictions: string;
  rate_limit_rps: number;
  mode: string;
}

export const api = {
  register: (email: string, password: string) =>
    request<AuthUser>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request<AuthUser>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request<AuthUser>("/auth/me"),
  getSkillMap: () => request<SkillMap>("/skills"),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  listSessions: () => request<AuthSession[]>("/auth/sessions"),
  revokeSession: (sessionId: number) => request<void>(`/auth/sessions/${sessionId}`, { method: "DELETE" }),
  listAuthEvents: () => request<AuthEvent[]>("/auth/events"),
  listPracticeLabs: () => request<PracticeLab[]>("/practice/labs"),
  getPracticeLab: (labId: string) => request<PracticeLab>(`/practice/labs/${encodeURIComponent(labId)}`),
  runPracticeRequest: practiceRequest,
  updatePracticeProgress: (projectId: number, invId: number, labId: string, status: "started" | "completed") =>
    request<Investigation>(`/projects/${projectId}/investigations/${invId}/practice/${encodeURIComponent(labId)}`, {
      method: "PUT", body: JSON.stringify({ status }),
    }),
  listProjects: () => request<Project[]>("/projects"),
  getProject: (id: number) => request<ProjectDetail>(`/projects/${id}`),
  createProject: (payload: CreateProjectPayload) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(payload) }),
  updateProject: (id: number, payload: Partial<Pick<Project, "mode" | "status" | "rate_limit_rps">>) =>
    request<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteProject: (id: number) => request<void>(`/projects/${id}`, { method: "DELETE" }),

  checkScope: (projectId: number, target: string) =>
    request<ScopeCheckResponse>(`/projects/${projectId}/scopeguard/check`, {
      method: "POST",
      body: JSON.stringify({ target }),
    }),
  scopeAuditLog: (projectId: number) =>
    request<ScopeAuditLogEntry[]>(`/projects/${projectId}/scopeguard/audit-log`),
  huntHistory: (projectId: number, category?: string) =>
    request<HuntHistory>(`/projects/${projectId}/history${category ? `?category=${encodeURIComponent(category)}` : ""}`),

  startRecon: (projectId: number) =>
    request<{ job: ReconJob; message: string }>(`/projects/${projectId}/recon/start`, { method: "POST" }),
  listReconJobs: (projectId: number) => request<ReconJob[]>(`/projects/${projectId}/recon/jobs`),
  getReconToolReference: (projectId: number) =>
    request<ReconToolReference>(`/projects/${projectId}/recon/tool-reference`),
  listAssets: (projectId: number) => request<Asset[]>(`/projects/${projectId}/assets`),
    listDiscoveredEndpoints: (projectId: number) => request<DiscoveredEndpoint[]>(`/projects/${projectId}/surface/endpoints`),
    getDiscoveredEndpoint: (projectId: number, endpointId: number) =>
      request<DiscoveredEndpoint>(`/projects/${projectId}/surface/endpoints/${endpointId}`),
    listCrawlRejections: (projectId: number) => request<CrawlRejection[]>(`/projects/${projectId}/surface/rejections`),
    listPublicMetadata: (projectId: number) =>
      request<PublicMetadataDocument[]>(`/projects/${projectId}/surface/metadata`),
  toggleAssetReviewed: (projectId: number, assetId: number) =>
    request<Asset>(`/projects/${projectId}/assets/${assetId}/reviewed`, { method: "PATCH" }),

  sendHttpRequest: (
    projectId: number,
    payload: {
      method: string;
      url: string;
      headers: Record<string, string>;
      body: string | null;
      identity_profile_id: number | null;
    },
  ) =>
    request<HttpTransaction>(`/projects/${projectId}/http/send`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listHttpTransactions: (projectId: number) => request<HttpTransaction[]>(`/projects/${projectId}/http/transactions`),
  getHttpTransaction: (projectId: number, txId: number) =>
    request<HttpTransaction>(`/projects/${projectId}/http/transactions/${txId}`),
  listIdentityProfiles: (projectId: number) =>
    request<IdentityProfile[]>(`/projects/${projectId}/identities`),
  createIdentityProfile: (
    projectId: number,
    payload: { name: string; description: string; headers: Record<string, string> },
  ) => request<IdentityProfile>(`/projects/${projectId}/identities`, {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  updateIdentityProfile: (projectId: number, profileId: number, payload: Partial<{
    name: string; description: string; headers: Record<string, string>; enabled: boolean;
  }>) => request<IdentityProfile>(`/projects/${projectId}/identities/${profileId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }),
  deleteIdentityProfile: (projectId: number, profileId: number) =>
    request<void>(`/projects/${projectId}/identities/${profileId}`, { method: "DELETE" }),

  analyzeJs: (projectId: number, url: string) =>
    request<JsFile>(`/projects/${projectId}/js/analyze`, { method: "POST", body: JSON.stringify({ url }) }),
  listJsFiles: (projectId: number) => request<JsFile[]>(`/projects/${projectId}/js/files`),

  getApiMap: (projectId: number) => request<ApiMap>(`/projects/${projectId}/api-map`),

  getParameterInventory: (projectId: number) =>
    request<ParameterInventory>(`/projects/${projectId}/parameters`),

  getAuthFlow: (projectId: number) => request<AuthFlow>(`/projects/${projectId}/auth-flow`),

  getAccessControlWorkbench: (projectId: number) =>
    request<AccessControlWorkbench>(`/projects/${projectId}/access-control/workbench`),

  analyzeTransaction: (projectId: number, txId: number) =>
    request<AnalyzerReport>(`/projects/${projectId}/analyzer/transactions/${txId}`),
  getAnalyzerSummary: (projectId: number) => request<AnalyzerSummary>(`/projects/${projectId}/analyzer/summary`),

  compareTransactions: (projectId: number, transactionAId: number, transactionBId: number) =>
    request<DiffResult>(
      `/projects/${projectId}/diff/compare?transaction_a_id=${transactionAId}&transaction_b_id=${transactionBId}`,
    ),
  listAccessControlScenarios: (projectId: number) =>
    request<AccessControlScenario[]>(`/projects/${projectId}/diff/scenarios`),
  createAccessControlScenario: (
    projectId: number,
    payload: { name: string; description: string; transaction_ids: number[] },
  ) => request<AccessControlScenario>(`/projects/${projectId}/diff/scenarios`, {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  updateAccessControlScenario: (
    projectId: number,
    scenarioId: number,
    payload: Partial<{ name: string; description: string; transaction_ids: number[] }>,
  ) => request<AccessControlScenario>(`/projects/${projectId}/diff/scenarios/${scenarioId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }),
  getAccessControlMatrix: (projectId: number, scenarioId: number) =>
    request<AccessControlMatrix>(`/projects/${projectId}/diff/scenarios/${scenarioId}`),
  createScenarioInvestigation: (
    projectId: number,
    scenarioId: number,
    selectedPairs: Array<{ transaction_a_id: number; transaction_b_id: number }>,
  ) => request<Investigation>(`/projects/${projectId}/diff/scenarios/${scenarioId}/investigation`, {
    method: "POST",
    body: JSON.stringify({ selected_pairs: selectedPairs }),
  }),
  deleteAccessControlScenario: (projectId: number, scenarioId: number) =>
    request<void>(`/projects/${projectId}/diff/scenarios/${scenarioId}`, { method: "DELETE" }),

  createInvestigation: (projectId: number, payload: CreateInvestigationPayload) =>
    request<Investigation>(`/projects/${projectId}/investigations`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listInvestigations: (projectId: number, status?: InvestigationStatus) =>
    request<Investigation[]>(`/projects/${projectId}/investigations${status ? `?status=${status}` : ""}`),
  getInvestigation: (projectId: number, invId: number) =>
    request<Investigation>(`/projects/${projectId}/investigations/${invId}`),
  updateInvestigation: (projectId: number, invId: number, payload: Partial<Investigation>) =>
    request<Investigation>(`/projects/${projectId}/investigations/${invId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteInvestigation: (projectId: number, invId: number) =>
    request<void>(`/projects/${projectId}/investigations/${invId}`, { method: "DELETE" }),

  uploadEvidence: (projectId: number, invId: number, file: File, caption: string) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("caption", caption);
    return uploadFile<EvidenceAttachment>(`/projects/${projectId}/investigations/${invId}/evidence`, formData);
  },
  listEvidence: (projectId: number, invId: number) =>
    request<EvidenceAttachment[]>(`/projects/${projectId}/investigations/${invId}/evidence`),
  updateEvidence: (
    projectId: number,
    invId: number,
    attachmentId: number,
    payload: { caption?: string; annotations?: EvidenceAnnotation[] },
  ) =>
    request<EvidenceAttachment>(
      `/projects/${projectId}/investigations/${invId}/evidence/${attachmentId}`,
      { method: "PATCH", body: JSON.stringify(payload) },
    ),
  replaceEvidenceImage: (projectId: number, invId: number, attachmentId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return uploadFile<EvidenceAttachment>(
      `/projects/${projectId}/investigations/${invId}/evidence/${attachmentId}/image`,
      formData,
      "PUT",
    );
  },
  deleteEvidence: (projectId: number, invId: number, attachmentId: number) =>
    request<void>(`/projects/${projectId}/investigations/${invId}/evidence/${attachmentId}`, { method: "DELETE" }),
  getEvidencePackage: (projectId: number, invId: number) =>
    request<EvidencePackage>(`/projects/${projectId}/investigations/${invId}/evidence/package`),
  downloadEvidenceBundle: (projectId: number, invId: number) =>
    downloadFile(
      `/projects/${projectId}/investigations/${invId}/evidence/export`,
      `vajra-investigation-${invId}-evidence.zip`,
    ),
  verifyEvidenceBundle: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return uploadFile<EvidenceBundleVerification>("/evidence/verify-bundle", formData);
  },

  createOrGetReport: (projectId: number, invId: number) =>
    request<Report>(`/projects/${projectId}/investigations/${invId}/report`, { method: "POST" }),
  getReport: (projectId: number, invId: number) =>
    request<Report>(`/projects/${projectId}/investigations/${invId}/report`),
  updateReport: (projectId: number, invId: number, payload: Partial<Report>) =>
    request<Report>(`/projects/${projectId}/investigations/${invId}/report`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  getReadiness: (projectId: number, invId: number) =>
    request<Readiness>(`/projects/${projectId}/investigations/${invId}/report/readiness`),

  askCopilot: (projectId: number, payload: AskCopilotPayload) =>
    request<AskCopilotResponse>(`/projects/${projectId}/copilot/ask`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  explainAsset: (assetId: number) =>
    request<Explanation>("/copilot/explain", {
      method: "POST",
      body: JSON.stringify({ kind: "asset", asset_id: assetId }),
    }),
  explainHeader: (headerName: string) =>
    request<Explanation>("/copilot/explain", {
      method: "POST",
      body: JSON.stringify({ kind: "header", header_name: headerName }),
    }),
  nextBestAction: (projectId: number) =>
    request<NextBestAction>(`/projects/${projectId}/copilot/next-best-action`),
};
