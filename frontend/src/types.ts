export type HuntMode = "guided" | "standard" | "advanced";
export type ProjectStatus = "active" | "paused" | "archived";

export interface Project {
  id: number;
  name: string;
  target: string;
  allowed_domains: string[];
  allowed_subdomains: string[];
  excluded_assets: string[];
  program_rules: string;
  testing_restrictions: string;
  rate_limit_rps: number;
  mode: HuntMode;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface ProjectStats {
  assets_discovered: number;
  live_hosts: number;
  high_priority_assets: number;
  recon_jobs_run: number;
  last_recon_at: string | null;
}

export interface ProjectDetail extends Project {
  stats: ProjectStats;
}

export type ScopeDecision = "allowed" | "blocked" | "manual_review";

export interface ScopeCheckResponse {
  target_input: string;
  normalized_target: string;
  decision: ScopeDecision;
  reason: string;
}

export interface ScopeAuditLogEntry {
  id: number;
  target_input: string;
  normalized_target: string;
  decision: ScopeDecision;
  reason: string;
  operation: string;
  created_at: string;
}

export interface HuntEvent {
  id: string;
  category: string;
  title: string;
  detail: string;
  status: string;
  occurred_at: string;
  href: string | null;
}

export interface HuntHistory {
  events: HuntEvent[];
  total: number;
  categories: Record<string, number>;
}

export type AssetType = "subdomain" | "host" | "url" | "api" | "javascript";
export type AssetSource = "crtsh" | "dns" | "manual";

export interface Asset {
  id: number;
  project_id: number;
  hostname: string;
  asset_type: AssetType;
  source: AssetSource;
  discovery_sources: string[];
  dns_records: Record<string, string[]>;
  resolved_ip: string | null;
  is_live: boolean | null;
  status_code: number | null;
  server_header: string | null;
  page_title: string | null;
  probe_source: string;
  technologies: string[];
  priority_score: number;
  priority_reasons: string[];
  priority_category: string | null;
  recommended_action: string | null;
  reviewed: boolean;
  discovered_at: string;
  last_checked_at: string | null;
}

export type ReconJobStatus = "pending" | "running" | "completed" | "failed" | "blocked";
export type ReconStage =
  | "subdomain_discovery"
  | "dns_resolution"
  | "live_host_probing"
  | "technology_detection"
  | "prioritization"
  | "done";

export interface ReconJob {
  id: number;
  project_id: number;
  status: ReconJobStatus;
  stage: ReconStage | null;
  started_at: string;
  completed_at: string | null;
  summary: Record<string, number>;
  notes: string[];
  error: string | null;
}

export interface Explanation {
  what_found: string;
  why_it_matters: string;
  what_to_check: string[];
  false_positive_notes: string[];
  evidence_needed: string[];
  mini_lesson_title: string | null;
  mini_lesson: string | null;
}

export interface HttpTransaction {
  id: number;
  project_id: number;
  identity_profile_id: number | null;
  identity_profile_name: string | null;
  profile_header_names: string[];
  method: string;
  url: string;
  request_headers: Record<string, string>;
  request_body: string | null;
  status_code: number | null;
  response_headers: Record<string, string>;
  response_cookies: string[];
  response_body: string | null;
  response_body_truncated: boolean;
  response_size_bytes: number | null;
  timing_ms: number | null;
  technologies: string[];
  interesting_indicators: string[];
  error: string | null;
  created_at: string;
}

export interface IdentityProfile {
  id: number;
  project_id: number;
  name: string;
  description: string;
  header_names: string[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export type JsFindingType =
  | "api_route"
  | "graphql_url"
  | "websocket_url"
  | "config_reference"
  | "source_map"
  | "potential_secret";

export interface JsFinding {
  id: number;
  finding_type: JsFindingType;
  value: string;
  context: string | null;
  metadata_: Record<string, string>;
}

export interface JsFile {
  id: number;
  project_id: number;
  url: string;
  status_code: number | null;
  size_bytes: number | null;
  error: string | null;
  fetched_at: string;
  findings: JsFinding[];
}

export interface Endpoint {
  pattern: string;
  category: string;
  methods: string[];
  sample_urls: string[];
  sources: string[];
  query_parameters: string[];
  tags: string[];
  security_schemes: string[];
  deprecated_methods: string[];
  operation_summaries: string[];
  has_object_identifier: boolean;
  interesting_score: number;
  reasons: string[];
  suggested_investigation: string;
}

export interface DiscoveredEndpoint {
  id: number;
  project_id: number;
  url: string;
  normalized_url: string;
  hostname: string;
  path: string;
  method: string;
  query_parameters: string[];
  parameter_details: Array<{ name: string; in: string; required: boolean; schema_type?: string }>;
  request_body_content_types: string[];
  security_requirements: Array<Record<string, string[]>>;
  tags: string[];
  operation_id: string | null;
  summary: string | null;
  deprecated: boolean;
  request_template: {
    headers?: Record<string, string>;
    body?: string | null;
    requires_manual_values?: string[];
    inert_placeholders?: boolean;
  };
  source: string;
  status_code: number | null;
  content_type: string | null;
  first_seen_at: string;
  last_seen_at: string;
}

export interface CrawlRejection {
  id: number;
  url: string;
  reason: string;
  source: string;
  created_at: string;
}

export interface PublicMetadataDocument {
  id: number;
  project_id: number;
  url: string;
  kind: "robots" | "sitemap" | "openapi";
  status_code: number | null;
  content_type: string | null;
  content_sha256: string | null;
  entries: Array<{ type: string; value: string; parameters?: string }>;
  error: string | null;
  fetched_at: string;
}

export interface ApiMap {
  categories: Record<string, Endpoint[]>;
  total_endpoints: number;
}

export interface ParameterInsight {
  name: string;
  classification: string;
  locations: string[];
  sources: string[];
  schema_types: string[];
  required: boolean;
  observed_endpoint_count: number;
  endpoints: string[];
  value_shapes: string[];
  review_areas: string[];
  note: string;
}

export interface ParameterInventory {
  parameters: ParameterInsight[];
  total_parameters: number;
}

export interface AuthFlowEndpoint {
  method: string;
  path: string;
  sources: string[];
  sample_url: string | null;
}

export interface AuthFlowStage {
  key: string;
  title: string;
  why: string;
  review_checks: string[];
  observed: boolean;
  endpoints: AuthFlowEndpoint[];
}

export interface AuthFlow {
  stages: AuthFlowStage[];
  observed_stage_count: number;
  total_stage_count: number;
  review_focus: string[];
  note: string;
}

export type AnalyzerClassification = "informational" | "interesting" | "needs_review" | "potential_finding";

export interface AnalyzerFinding {
  category: string;
  classification: AnalyzerClassification;
  title: string;
  description: string;
  evidence: string[];
}

export interface AnalyzerReport {
  transaction_id: number;
  url: string;
  findings: AnalyzerFinding[];
  counts: Record<AnalyzerClassification, number>;
}

export interface NotableFinding {
  transaction_id: number | null;
  url: string;
  source: "http_transaction" | "public_metadata";
  finding: AnalyzerFinding;
}

export interface AnalyzerSummary {
  transactions_analyzed: number;
  metadata_documents_analyzed: number;
  counts: Record<AnalyzerClassification, number>;
  notable_findings: NotableFinding[];
}

export interface HeaderDiffEntry {
  header: string;
  value_a: string | null;
  value_b: string | null;
}

export interface DiffFinding {
  confidence: number;
  category: string;
  notes: string[];
}

export interface DiffResult {
  transaction_a_id: number;
  transaction_b_id: number;
  url_a: string;
  url_b: string;
  normalized_pattern: string | null;
  same_endpoint_pattern: boolean;
  same_identity: boolean;
  identity_a: string;
  identity_b: string;
  identity_basis: string;
  status_a: number | null;
  status_b: number | null;
  status_match: boolean;
  length_a: number | null;
  length_b: number | null;
  header_differences: HeaderDiffEntry[];
  body_keys_only_in_a: string[];
  body_keys_only_in_b: string[];
  body_common_keys: string[];
  finding: DiffFinding;
}

export interface AccessControlScenario {
  id: number;
  project_id: number;
  name: string;
  description: string;
  transaction_ids: number[];
  created_at: string;
  updated_at: string;
}

export interface ScenarioTransaction {
  id: number;
  method: string;
  url: string;
  normalized_pattern: string;
  identity_name: string;
  identity_profile_id: number | null;
  controlled_identity: boolean;
  status_code: number | null;
  error: boolean;
}

export interface ScenarioMatrixCell {
  transaction_a_id: number;
  transaction_b_id: number;
  same_endpoint_pattern: boolean;
  same_identity: boolean;
  status_match: boolean;
  confidence: number;
  category: string;
}

export interface AccessControlSnapshotCell {
  transaction_a_id: number;
  transaction_b_id: number;
  identity_a: string;
  identity_b: string;
  identity_basis: string;
  url_a: string;
  url_b: string;
  pattern_a: string;
  pattern_b: string;
  status_a: number | null;
  status_b: number | null;
  same_endpoint_pattern: boolean;
  same_identity: boolean;
  status_match: boolean;
  confidence: number;
  category: string;
}

export interface AccessControlSnapshot {
  schema_version?: number;
  captured_at?: string;
  scenario_id?: number;
  scenario_name?: string;
  scenario_description?: string;
  warnings?: string[];
  selected_cells?: AccessControlSnapshotCell[];
}

export interface AccessControlMatrix {
  scenario: AccessControlScenario;
  transactions: ScenarioTransaction[];
  cells: ScenarioMatrixCell[];
  warnings: string[];
}

export type InvestigationStatus = "open" | "false_positive" | "validated" | "closed";
export type InvestigationSource = "asset" | "analyzer_finding" | "diff_result" | "manual";

export interface Investigation {
  id: number;
  project_id: number;
  title: string;
  target: string;
  endpoint: string;
  status: InvestigationStatus;
  source: InvestigationSource;
  source_reference: Record<string, unknown>;
  ai_notes: string;
  confidence: number;
  linked_transaction_ids: number[];
  linked_asset_id: number | null;
  access_control_scenario_id: number | null;
  access_control_snapshot: AccessControlSnapshot;
  notes: string;
  false_positive_checklist: Record<string, boolean | null>;
  impact_observed: string;
  impact_potential: string;
  practice_progress: Record<string, "started" | "completed">;
  recommended_practice_labs: string[];
  created_at: string;
  updated_at: string;
  missing_evidence: string[];
  false_positive_hint: string | null;
  false_positive_questions: Record<string, string>;
}

export interface CreateInvestigationPayload {
  title: string;
  target?: string;
  endpoint?: string;
  source?: InvestigationSource;
  source_reference?: Record<string, unknown>;
  ai_notes?: string;
  confidence?: number;
  linked_transaction_ids?: number[];
  linked_asset_id?: number | null;
}

export interface EvidenceAttachment {
  id: number;
  project_id: number;
  investigation_id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  caption: string;
  uploaded_at: string;
  url: string;
}

export interface MaskedTransaction {
  id: number;
  identity_profile_name: string | null;
  method: string;
  url: string;
  request_headers: Record<string, string>;
  request_body: string | null;
  status_code: number | null;
  response_headers: Record<string, string>;
  response_cookies: string[];
  response_body: string | null;
  created_at: string;
  masking_verifiable: boolean;
}

export interface EvidencePackage {
  investigation_id: number;
  access_control_snapshot: AccessControlSnapshot;
  transactions: MaskedTransaction[];
  attachments: EvidenceAttachment[];
}

export interface VerifiedBundleFile {
  path: string;
  size_bytes: number;
  compressed_size_bytes: number;
  category: string | null;
  safe_path: boolean;
  checksum_status: "matched" | "mismatch" | "not_listed" | string;
}

export interface EvidenceBundleVerification {
  filename: string;
  valid: boolean;
  archive_safe: boolean;
  manifest_valid: boolean;
  checksums_valid: boolean;
  compressed_size_bytes: number;
  uncompressed_size_bytes: number;
  file_count: number;
  project: Record<string, unknown> | null;
  investigation: Record<string, unknown> | null;
  masking: Record<string, unknown> | null;
  files: VerifiedBundleFile[];
  warnings: string[];
  errors: string[];
}

export interface Report {
  id: number;
  investigation_id: number;
  summary: string;
  prerequisites: string;
  steps_to_reproduce: string;
  observed_behavior: string;
  expected_behavior: string;
  suggested_remediation: string;
  created_at: string;
  updated_at: string;
}

export interface ReadinessCheck {
  label: string;
  passed: boolean;
  points: number;
}

export interface Readiness {
  score: number;
  checks: ReadinessCheck[];
  missing: string[];
}

export interface AskCopilotPayload {
  question: string;
  investigation_id?: number;
  asset_id?: number;
  transaction_id?: number;
}

export interface AskCopilotResponse {
  answer: string;
  provider: string;
}

export interface NextBestAction {
  headline: string;
  reason: string;
  recommended_asset_id: number | null;
  recommended_hostname: string | null;
  alternatives: string[];
}

export interface PracticeLab {
  id: string;
  title: string;
  concept_category: string;
  mini_lesson_title: string;
  mini_lesson: string;
  try_it_steps: string[];
  base_path: string;
  title_te: string;
  mini_lesson_title_te: string;
  mini_lesson_te: string;
  try_it_steps_te: string[];
}

export interface PracticeResponse {
  status: number;
  statusText: string;
  headers: Record<string, string>;
  body: string;
}

export interface AuthUser {
  id: number;
  email: string;
  created_at: string;
}

export interface AuthSession {
  id: number;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  ip_address: string;
  user_agent: string;
  current: boolean;
}

export interface AuthEvent {
  id: number;
  event_type: string;
  success: boolean;
  ip_address: string;
  created_at: string;
}
