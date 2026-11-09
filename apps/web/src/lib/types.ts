export interface Me { id: string; username: string; display_name: string; org_id: string; org_role: string; project_roles: Record<string, string>;
  orgs: { id: string; name: string; role: string }[]; preferences: { preferred_model?: string; theme?: string; favorite_projects?: string[] } }
export interface Project { id: string; slug: string; title: string; purpose: string; tags: string[]; status: string; revision: number;
  created_at: string; my_role?: string | null; environments?: { id: string; name: string }[] }
export interface Freshness { status: "current" | "stale" | "incomplete" | "unknown"; reason?: string; age_s?: number }
export interface Connector { id: string; kind: string; name: string; config: Record<string, unknown>; enabled: boolean; has_secret: boolean;
  freshness_sla_s: number; last_status: string; last_complete_at?: string; last_scan_id?: string; freshness: Freshness }
export interface Scan { id: string; connector_id: string; status: string; ref?: string; revision?: string; created_at: string; finished_at?: string;
  stats: Record<string, unknown>; error?: string }
export interface Evidence { observation_id: string; connector_id?: string; origin: string; source_ref: string; source_revision: string;
  observed_at: string; parser_version: string; confidence: number; span: { path?: string; line_start?: number; line_end?: number } }
export interface GNode { key: string; kind: string; name: string; attributes: Record<string, any>; origins: string[]; confidence: number;
  evidence: Evidence[]; inferred_only: boolean; sensitive?: boolean; by_origin?: Record<string, Record<string, any>> }
export interface GEdge { key: string; kind: string; source: string; target: string; attributes: Record<string, any>; origins: string[];
  confidence: number; evidence: Evidence[]; inferred_only: boolean }
export interface Snapshot { id: string; version: number; manifest_hash: string; node_count: number; edge_count: number; created_at: string; trigger: string;
  inputs?: any }
export interface ViewNode { element_kind?: string; id: string; kind: string; name: string; technology: string; subtype: string; description: string; owner: string;
  origins: string[]; confidence: number; inferred_only: boolean; primary: boolean; zoom: string | null; evidence_count: number; focal: boolean;
  focal_reason?: string; state?: string; member_keys?: string[]; components?: number; children?: number }
export interface ViewEdge { id: string; source: string; target: string; kind: string; label: string; protocols: string[]; count: number;
  origins: string[]; confidence: number; inferred_only: boolean; members: string[]; focal: boolean }
export interface View { view_key: string; level: number; title: string; breadcrumbs: { key: string; title: string }[]; nodes: ViewNode[];
  edges: ViewEdge[]; detail_views: { key: string; title: string; count: number }[]; budget: { primary: number; max: number; split: boolean };
  empty_reason?: string; snapshot: { id: string; version: number; manifest_hash: string }; layout: { overrides: Record<string, { x: number; y: number }>; revision: number } }
export interface Finding { id: string; rule_id: string; rule_version: string; subject_key: string; title: string; severity: string; verdict: string;
  status: string; expected: any; actual: any; evidence: Evidence[]; first_seen: string; last_seen: string; occurrences: number;
  suppressed_until?: string; resolution_note: string; comments?: { id: string; username: string; body: string; created_at: string }[];
  rule?: { id: string; title: string; version: string } }
export interface Adr { id: string; number: number; title: string; status: string; author?: string; approver?: string; author_id: string;
  ai_drafted: boolean; created_at: string; decided_at?: string; current?: { version: number; content: any; links: string[] }; versions?: any[] }
