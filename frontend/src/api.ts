const jsonHeaders = { "Content-Type": "application/json" };

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(path, { credentials: "include" });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method: "POST", credentials: "include" };
  if (body !== undefined) {
    init.headers = jsonHeaders;
    init.body = JSON.stringify(body);
  }
  const r = await fetch(path, init);
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<T>;
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "PATCH",
    headers: jsonHeaders,
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<T>;
}

export async function apiDelete<T>(path: string): Promise<T> {
  const r = await fetch(path, { method: "DELETE", credentials: "include" });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<T>;
}

export type Me = {
  person_id: string | null;
  name: string | null;
  email: string | null;
  active_tenant_id: string;
  allowed_tenant_ids: string[];
  permissions_admin: boolean;
};

export async function setActiveTenant(tenantId: string): Promise<void> {
  await apiPost("/api/auth/active-tenant", { tenant_id: tenantId });
}

export type MeFetchResult =
  | { state: "ok"; me: Me }
  | { state: "unauthorized" }
  | { state: "forbidden" };

export async function fetchMe(): Promise<MeFetchResult> {
  const r = await fetch("/api/me", { credentials: "include" });
  if (r.status === 401) return { state: "unauthorized" };
  if (r.status === 403) return { state: "forbidden" };
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return { state: "ok", me: (await r.json()) as Me };
}

export type Org = {
  id: string;
  name: string;
  org_type: string;
  parent_id?: string | null;
};

/** Phone for Directory list/lookup: number plus extension when present. */
export function formatPublicPhone(
  phone: string | null | undefined,
  ext: string | null | undefined,
): string {
  const p = (phone ?? "").trim();
  const e = (ext ?? "").trim();
  if (p && e) return `${p} ext. ${e}`;
  if (p) return p;
  if (e) return `ext. ${e}`;
  return "—";
}

export type PersonRow = {
  id: string;
  /** Present when the row is one assignment in an org; use this as the React list key. */
  assignment_id?: string | null;
  full_name: string | null;
  email_public: string | null;
  phone_public: string | null;
  phone_public_ext: string | null;
  assignment_job_title: string | null;
  /** Org + title labels when listing all people (not org-scoped). */
  assignment_summary?: string | null;
  assignment_count?: number | null;
  /** Whether the person appears in public directory surfaces (e.g. print). */
  show_in_directory?: boolean | null;
};

/** Person with no assignment in a given org (for role assign picker). */
export type UnassignedPersonRow = {
  id: string;
  full_name: string | null;
  email_public: string | null;
  phone_public: string | null;
  phone_public_ext: string | null;
};

export type OrgAssignment = {
  id: string;
  job_title: string | null;
  status: string | null;
  seat_no: number | null;
  person_id: string | null;
  person_full_name: string | null;
  person_email: string | null;
};

export type OpenAssignment = {
  id: string;
  job_title: string | null;
  status: string | null;
  seat_no: number | null;
  org_id: string;
  org_name: string | null;
};

export type AuditItem = {
  id: number;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  details: Record<string, unknown> | null;
  ts: string;
};

export type PrintEntry = {
  name: string;
  title: string | null;
  phone: string | null;
  email: string | null;
};

export type PrintDepartment = {
  department: string;
  parent_group: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  entries: PrintEntry[];
};

export async function fetchPrintDirectory(): Promise<PrintDepartment[]> {
  return apiGet<PrintDepartment[]>("/api/directory/print");
}

export type Cap = {
  id: string;
  cap_key: string;
  cap_label: string;
  description: string | null;
};

export type PersonCap = {
  cap_key: string;
  cap_label: string;
  description: string | null;
  granted_at: string;
  granted_by: string | null;
};

export type PersonSearchResult = {
  id: string;
  full_name: string | null;
  name_first: string | null;
  name_last: string | null;
  email_public: string | null;
};

export async function fetchCaps(): Promise<Cap[]> {
  const r = await apiGet<{ items: Cap[] }>("/api/permissions/caps");
  return r.items;
}

export async function searchPeopleForPermissions(
  q: string,
): Promise<PersonSearchResult[]> {
  const r = await apiGet<{ items: PersonSearchResult[] }>(
    `/api/permissions/people?q=${encodeURIComponent(q)}`,
  );
  return r.items;
}

export async function fetchPersonCaps(personId: string): Promise<PersonCap[]> {
  const r = await apiGet<{ items: PersonCap[] }>(
    `/api/permissions/people/${personId}/caps`,
  );
  return r.items;
}

export async function grantPersonCap(
  personId: string,
  capKey: string,
): Promise<void> {
  await apiPost(`/api/permissions/people/${personId}/caps`, { cap_key: capKey });
}

export async function revokePersonCap(
  personId: string,
  capKey: string,
): Promise<void> {
  await apiDelete(`/api/permissions/people/${personId}/caps/${capKey}`);
}
