<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { apiGet, apiPatch, apiPost, formatPublicPhone, type Org, type PersonRow } from "../api";
import OrgPanel from "../components/OrgPanel.vue";
import PersonPanel from "../components/PersonPanel.vue";

type NewPersonForm = {
  name_first: string;
  name_last: string;
  email_public: string;
  show_in_directory: boolean;
};

const BLANK_PERSON: NewPersonForm = {
  name_first: "",
  name_last: "",
  email_public: "",
  show_in_directory: false,
};

type DriftPerson = { id: string; name: string };
type DriftOrg = { id?: string; name: string; taxonomy?: string };
type DriftHierarchyMismatch = {
  id: string;
  name: string;
  taxonomy?: string;
  directory_parent_id?: string | null;
  directory_parent_name?: string | null;
  wordpress_parent_id?: string | null;
  wordpress_parent_name?: string | null;
};
type DriftAssignment = {
  person_id: string;
  person_name: string;
  missing_in_wp: { name: string }[];
  extra_in_wp: { name: string }[];
};
type DriftNameMismatch = { id: string; directory_name: string; wordpress_name: string };
type DriftContactFieldDiff = { directory: string; wordpress: string };
type DriftContactMismatch = { id: string; name: string; fields: Record<string, DriftContactFieldDiff> };
type DriftReport = {
  summary?: {
    people_missing_in_wp?: number;
    people_extra_in_wp?: number;
    orgs_missing_in_wp?: number;
    orgs_extra_in_wp?: number;
    org_hierarchy_mismatch?: number;
    assignment_mismatches?: number;
    people_name_mismatch?: number;
    people_contact_mismatch?: number;
  };
  people_missing_in_wp?: DriftPerson[];
  people_extra_in_wp?: DriftPerson[];
  orgs_missing_in_wp?: DriftOrg[];
  orgs_extra_in_wp?: DriftOrg[];
  org_hierarchy_mismatch?: DriftHierarchyMismatch[];
  assignment_mismatches?: DriftAssignment[];
  people_name_mismatch?: DriftNameMismatch[];
  people_contact_mismatch?: DriftContactMismatch[];
};

function driftTotal(report: DriftReport | null): number {
  const s = report?.summary;
  if (!s) return 0;
  return (
    (s.people_missing_in_wp ?? 0) +
    (s.people_extra_in_wp ?? 0) +
    (s.orgs_missing_in_wp ?? 0) +
    (s.orgs_extra_in_wp ?? 0) +
    (s.org_hierarchy_mismatch ?? 0) +
    (s.assignment_mismatches ?? 0) +
    (s.people_name_mismatch ?? 0) +
    (s.people_contact_mismatch ?? 0)
  );
}

function formatHierarchyParent(name: string | null | undefined, id: string | null | undefined): string {
  if (name && name.trim()) return name.trim();
  if (id && id.trim()) return id.trim();
  return "(top-level)";
}

function formatContactDiff(fields: Record<string, DriftContactFieldDiff>): string {
  return Object.entries(fields)
    .map(([key, diff]) => {
      const dir = diff.directory || "(empty)";
      const wp = diff.wordpress || "(empty)";
      return `${key}: directory “${dir}” vs website “${wp}”`;
    })
    .join("; ");
}

type OrgTab = "department" | "board" | "local_unit" | "external" | "all";

const TAB_LABELS: Record<OrgTab, string> = {
  department: "Departments & Offices",
  board: "Boards & Committees",
  local_unit: "Local Units",
  external: "External",
  all: "All",
};

const TAB_ORDER: OrgTab[] = ["department", "board", "local_unit", "external", "all"];

const ORG_CREATE_OPTIONS = [
  { value: "department", label: "Department / Office" },
  { value: "board", label: "Board / Committee / Commission" },
  { value: "local_unit", label: "Local Unit (City / Township / Village)" },
  { value: "county", label: "County" },
  { value: "external", label: "External Organization" },
] as const;

function defaultOrgTypeForTab(tab: OrgTab): string {
  if (tab === "department") return "department";
  if (tab === "board") return "board";
  if (tab === "local_unit") return "local_unit";
  if (tab === "external") return "external";
  return "board";
}

function orgTab(org_type: string): OrgTab {
  if (org_type === "board" || org_type === "committee" || org_type === "authority" || org_type === "task_force") return "board";
  if (org_type === "local_unit" || org_type === "city" || org_type === "township" || org_type === "village") return "local_unit";
  if (org_type === "external" || org_type === "external_org") return "external";
  return "department";
}

function peopleListPath(orgId: string | null, search: string, unassignedOnly: boolean): string {
  const params = new URLSearchParams();
  if (search) params.set("q", search);
  if (!orgId && unassignedOnly) params.set("unassigned", "true");
  const qs = params.toString() ? `?${params.toString()}` : "";
  return orgId ? `/api/orgs/${orgId}/people${qs}` : `/api/people${qs}`;
}

const orgs = ref<Org[]>([]);
const activeTab = ref<OrgTab>("department");
const orgFilter = ref("");
const selectedOrgId = ref<string | null>(null);
const unassignedOnly = ref(false);
const people = ref<PersonRow[]>([]);
const total = ref(0);
const search = ref("");
const debouncedSearch = ref("");
const loading = ref(true);
const err = ref<string | null>(null);
const selectedPersonId = ref<string | null>(null);
const orgEditorOpen = ref(false);
const syncBusy = ref(false);
const syncNotice = ref<{ kind: "ok" | "err"; text: string } | null>(null);
const driftBusy = ref(false);
const driftReport = ref<DriftReport | null>(null);
const driftErr = ref<string | null>(null);
const showInDirBusyId = ref<string | null>(null);
const addPersonOpen = ref(false);
const newPersonForm = ref<NewPersonForm>({ ...BLANK_PERSON });
const addPersonBusy = ref(false);
const addPersonErr = ref<string | null>(null);
const addOrgOpen = ref(false);
const newOrgForm = ref({ name: "", org_type: "department" });
const addOrgBusy = ref(false);
const addOrgErr = ref<string | null>(null);

watch(search, (v, _old, onCleanup) => {
  const t = setTimeout(() => {
    debouncedSearch.value = v.trim();
  }, 300);
  onCleanup(() => clearTimeout(t));
});

async function loadOrgs(preferSelectId?: string | null) {
  const r = await apiGet<{ items: Org[] }>("/api/orgs");
  orgs.value = r.items;
  const cur = selectedOrgId.value;
  if (preferSelectId && r.items.some((o) => o.id === preferSelectId)) selectedOrgId.value = preferSelectId;
  else if (cur && r.items.some((o) => o.id === cur)) selectedOrgId.value = cur;
  else selectedOrgId.value = null;
}

onMounted(() => {
  loadOrgs()
    .catch((e) => {
      err.value = String(e);
    })
    .finally(() => {
      loading.value = false;
    });
});

watch([selectedOrgId, debouncedSearch, unassignedOnly], (_n, _o, onCleanup) => {
  selectedPersonId.value = null;
  orgEditorOpen.value = false;
  people.value = [];
  total.value = 0;
  err.value = null;
  let cancelled = false;
  apiGet<{ items: PersonRow[]; total: number }>(peopleListPath(selectedOrgId.value, debouncedSearch.value, unassignedOnly.value))
    .then((r) => {
      if (!cancelled) {
        people.value = r.items;
        total.value = r.total;
      }
    })
    .catch((e) => {
      if (!cancelled) err.value = e instanceof Error ? e.message : "Failed to load people";
    });
  onCleanup(() => {
    cancelled = true;
  });
});

watch([activeTab, orgs], () => {
  const cur = selectedOrgId.value;
  if (cur === null) return;
  const visible = activeTab.value === "all" ? orgs.value : orgs.value.filter((o) => orgTab(o.org_type) === activeTab.value);
  if (!visible.some((o) => o.id === cur)) selectedOrgId.value = null;
});

const tabOrgs = computed(() => {
  if (activeTab.value === "all") return orgs.value;
  return orgs.value.filter((o) => orgTab(o.org_type) === activeTab.value);
});

const filteredOrgs = computed(() => {
  const s = orgFilter.value.toLowerCase();
  if (!s) return tabOrgs.value;
  return tabOrgs.value.filter((o) => o.name && o.name.toLowerCase().includes(s));
});

async function loadPeople() {
  err.value = null;
  try {
    const r = await apiGet<{ items: PersonRow[]; total: number }>(
      peopleListPath(selectedOrgId.value, debouncedSearch.value, unassignedOnly.value),
    );
    people.value = r.items;
    total.value = r.total;
  } catch (e) {
    err.value = e instanceof Error ? e.message : "Failed to load people";
  }
}

async function patchShowInDirectory(personId: string, next: boolean) {
  showInDirBusyId.value = personId;
  err.value = null;
  try {
    await apiPatch(`/api/people/${personId}`, { show_in_directory: next });
    people.value = people.value.map((r) => (r.id === personId ? { ...r, show_in_directory: next } : r));
  } catch (e) {
    err.value = e instanceof Error ? e.message : "Could not update directory visibility.";
  } finally {
    showInDirBusyId.value = null;
  }
}

async function doAddOrg() {
  const name = newOrgForm.value.name.trim();
  if (!name) {
    addOrgErr.value = "Enter an organization name.";
    return;
  }
  addOrgBusy.value = true;
  addOrgErr.value = null;
  err.value = null;
  try {
    const res = await apiPost<{ ok?: boolean; organization?: { id: string } }>("/api/orgs", {
      name,
      org_type: newOrgForm.value.org_type,
    });
    const newId = res.organization?.id;
    addOrgOpen.value = false;
    newOrgForm.value = { name: "", org_type: defaultOrgTypeForTab(activeTab.value) };
    await loadOrgs(newId ?? null);
    orgEditorOpen.value = false;
    orgFilter.value = "";
  } catch (e) {
    addOrgErr.value = e instanceof Error ? e.message : "Failed to create organization";
  } finally {
    addOrgBusy.value = false;
  }
}

async function doAddPerson() {
  addPersonBusy.value = true;
  addPersonErr.value = null;
  try {
    await apiPost("/api/people", {
      name_first: newPersonForm.value.name_first || null,
      name_last: newPersonForm.value.name_last || null,
      email_public: newPersonForm.value.email_public || null,
      show_in_directory: newPersonForm.value.show_in_directory,
    });
    addPersonOpen.value = false;
    newPersonForm.value = { ...BLANK_PERSON };
    await loadPeople();
  } catch (e) {
    addPersonErr.value = e instanceof Error ? e.message : "Failed to create person";
  } finally {
    addPersonBusy.value = false;
  }
}

function selectTab(tab: OrgTab) {
  activeTab.value = tab;
  orgFilter.value = "";
  orgEditorOpen.value = false;
  addOrgOpen.value = false;
}

function toggleAddOrg() {
  addOrgOpen.value = !addOrgOpen.value;
  addOrgErr.value = null;
  if (addOrgOpen.value) newOrgForm.value = { name: "", org_type: defaultOrgTypeForTab(activeTab.value) };
}

function selectAllPeople() {
  selectedOrgId.value = null;
  orgEditorOpen.value = false;
  selectedPersonId.value = null;
}

function selectOrg(id: string) {
  selectedOrgId.value = id;
  orgEditorOpen.value = false;
  selectedPersonId.value = null;
}

function selectPersonRow(p: PersonRow) {
  orgEditorOpen.value = false;
  addPersonOpen.value = false;
  selectedPersonId.value = p.id;
}

async function pushIncrementalSync() {
  syncNotice.value = null;
  syncBusy.value = true;
  try {
    const res = await apiPost<{ ok: boolean; wordpress?: unknown }>("/api/wordpress/incremental-sync");
    syncNotice.value = { kind: "ok", text: res.ok ? "WordPress incremental sync completed." : "Sync request finished." };
  } catch (e) {
    syncNotice.value = { kind: "err", text: e instanceof Error ? e.message : String(e) };
  } finally {
    syncBusy.value = false;
  }
}

async function checkDrift() {
  driftErr.value = null;
  driftBusy.value = true;
  try {
    const res = await apiPost<{ ok: boolean; wordpress?: DriftReport }>("/api/wordpress/reconciliation-report");
    driftReport.value = res.wordpress ?? {};
  } catch (e) {
    driftReport.value = null;
    driftErr.value = e instanceof Error ? e.message : String(e);
  } finally {
    driftBusy.value = false;
  }
}
</script>

<template>
  <div class="directory-layout">
    <aside class="org-sidebar">
      <div class="org-sidebar-header">
        <nav class="org-tabs" aria-label="Organization type">
          <button
            v-for="tab in TAB_ORDER"
            :key="tab"
            type="button"
            :class="['org-tab', { active: activeTab === tab }]"
            @click="selectTab(tab)"
          >
            {{ TAB_LABELS[tab] }}
          </button>
        </nav>
        <div class="org-sidebar-actions">
          <button type="button" class="btn ghost" @click="toggleAddOrg">{{ addOrgOpen ? "Cancel" : "+ Add organization" }}</button>
          <button type="button" class="btn ghost" :disabled="!selectedOrgId" @click="selectedPersonId = null; orgEditorOpen = true">
            Edit organization…
          </button>
        </div>
        <div v-if="addOrgOpen" class="add-org-form">
          <h4>New organization</h4>
          <p v-if="addOrgErr" class="error-msg">{{ addOrgErr }}</p>
          <div class="form-grid form-grid--twocol">
            <label class="span-2">
              Name
              <input class="field-input" v-model="newOrgForm.name" placeholder="e.g. Zoning Board of Appeals" />
            </label>
            <label class="span-2">
              Type
              <select class="field-input" v-model="newOrgForm.org_type">
                <option v-for="o in ORG_CREATE_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
              </select>
            </label>
          </div>
          <p class="muted small">A URL slug is created from the name. You can change details (phone, address, parent org, etc.) after saving via Edit organization.</p>
          <div class="form-actions">
            <button type="button" class="btn primary" :disabled="addOrgBusy" @click="doAddOrg">{{ addOrgBusy ? "Creating…" : "Create organization" }}</button>
          </div>
        </div>
        <input type="search" placeholder="Filter list…" class="field-input org-sidebar-filter" v-model="orgFilter" />
      </div>
      <div class="org-sidebar-scroll">
        <ul class="org-list">
          <li class="org-list-all">
            <button type="button" :class="selectedOrgId === null ? 'org-pill active' : 'org-pill'" @click="selectAllPeople">
              <span class="org-name">All people</span>
              <span class="org-meta">{{ unassignedOnly ? "Unassigned to any role" : "Every person in this tenant" }}</span>
            </button>
          </li>
          <li v-for="o in filteredOrgs" :key="o.id">
            <button type="button" :class="o.id === selectedOrgId ? 'org-pill active' : 'org-pill'" @click="selectOrg(o.id)">
              <span class="org-name">{{ o.name || "—" }}</span>
              <span class="org-meta">{{ o.org_type }}</span>
            </button>
          </li>
        </ul>
      </div>
    </aside>

    <section class="people-section">
      <div class="toolbar">
        <h2>{{ selectedOrgId === null ? (unassignedOnly ? "Unassigned people" : "All people") : "People" }}</h2>
        <span class="muted">
          <template v-if="selectedOrgId">{{ total }} shown in this org</template>
          <template v-else-if="unassignedOnly">{{ total }} with no role</template>
          <template v-else>{{ total }} people</template>
          <template v-if="total > people.length"> (showing {{ people.length }})</template>
        </span>
        <label v-if="selectedOrgId === null" class="checkbox-row">
          <input type="checkbox" v-model="unassignedOnly" />
          Unassigned to any role
        </label>
        <button type="button" class="btn ghost" @click="addPersonOpen = !addPersonOpen; addPersonErr = null">
          {{ addPersonOpen ? "Cancel" : "+ Add person" }}
        </button>
        <button type="button" class="btn ghost" :disabled="syncBusy" title="Runs County Core incremental sync on the website for this tenant" @click="pushIncrementalSync">
          {{ syncBusy ? "Syncing…" : "Push to county website" }}
        </button>
        <button type="button" class="btn ghost" :disabled="driftBusy" title="Compare Directory to WordPress without changing anything" @click="checkDrift">
          {{ driftBusy ? "Checking…" : "Check website drift" }}
        </button>
        <input type="search" placeholder="Search name or email…" class="field-input search-wide" v-model="search" />
      </div>

      <div v-if="addPersonOpen" class="add-person-form">
        <h4>New person</h4>
        <p v-if="addPersonErr" class="error-msg">{{ addPersonErr }}</p>
        <div class="form-grid form-grid--twocol">
          <label>First name<input class="field-input" v-model="newPersonForm.name_first" /></label>
          <label>Last name<input class="field-input" v-model="newPersonForm.name_last" /></label>
          <label class="span-2">Email<input class="field-input" type="email" v-model="newPersonForm.email_public" /></label>
          <label class="checkbox-row">
            <input type="checkbox" v-model="newPersonForm.show_in_directory" />
            Show in directory
          </label>
        </div>
        <div class="form-actions">
          <button type="button" class="btn primary" :disabled="addPersonBusy" @click="doAddPerson">{{ addPersonBusy ? "Adding…" : "Add person" }}</button>
        </div>
      </div>

      <p v-if="driftErr" class="error-msg">{{ driftErr }}</p>
      <div v-if="driftReport" class="drift-report">
        <div class="drift-report-head">
          <h3>
            {{ driftTotal(driftReport) === 0 ? "Directory and WordPress match" : `${driftTotal(driftReport)} difference${driftTotal(driftReport) === 1 ? "" : "s"} vs WordPress` }}
          </h3>
          <button type="button" class="btn ghost small" @click="driftReport = null">Dismiss</button>
        </div>
        <p class="muted">Read-only. Use “Push this person to website” or a full sync to fix a row.</p>
        <div v-if="(driftReport.people_missing_in_wp?.length ?? 0) > 0" class="drift-section">
          <h4>In Directory, missing on website</h4>
          <ul>
            <li v-for="p in driftReport.people_missing_in_wp" :key="p.id">
              <button type="button" class="linkish" @click="selectedPersonId = p.id">{{ p.name || p.id }}</button>
            </li>
          </ul>
        </div>
        <div v-if="(driftReport.people_extra_in_wp?.length ?? 0) > 0" class="drift-section">
          <h4>On website, not in Directory (or archived)</h4>
          <ul>
            <li v-for="p in driftReport.people_extra_in_wp" :key="p.id">{{ p.name || p.id }}</li>
          </ul>
        </div>
        <div v-if="(driftReport.people_name_mismatch?.length ?? 0) > 0" class="drift-section">
          <h4>Name mismatch</h4>
          <ul>
            <li v-for="p in driftReport.people_name_mismatch" :key="p.id">
              <button type="button" class="linkish" @click="selectedPersonId = p.id">{{ p.directory_name }}</button>
              on website as “{{ p.wordpress_name }}”
            </li>
          </ul>
        </div>
        <div v-if="(driftReport.people_contact_mismatch?.length ?? 0) > 0" class="drift-section">
          <h4>Contact info mismatch</h4>
          <ul>
            <li v-for="p in driftReport.people_contact_mismatch" :key="p.id">
              <button type="button" class="linkish" @click="selectedPersonId = p.id">{{ p.name || p.id }}</button>
              — {{ formatContactDiff(p.fields || {}) }}
            </li>
          </ul>
        </div>
        <div v-if="(driftReport.orgs_missing_in_wp?.length ?? 0) > 0" class="drift-section">
          <h4>Organizations missing on website</h4>
          <ul>
            <li v-for="o in driftReport.orgs_missing_in_wp" :key="o.id || o.name">{{ o.name }}{{ o.taxonomy ? ` (${o.taxonomy})` : "" }}</li>
          </ul>
        </div>
        <div v-if="(driftReport.orgs_extra_in_wp?.length ?? 0) > 0" class="drift-section">
          <h4>Organizations on website not in Directory</h4>
          <ul>
            <li v-for="o in driftReport.orgs_extra_in_wp" :key="o.id || o.name">{{ o.name }}{{ o.taxonomy ? ` (${o.taxonomy})` : "" }}</li>
          </ul>
        </div>
        <div v-if="(driftReport.org_hierarchy_mismatch?.length ?? 0) > 0" class="drift-section">
          <h4>Organization hierarchy mismatch</h4>
          <ul>
            <li v-for="o in driftReport.org_hierarchy_mismatch" :key="o.id">
              {{ o.name }}{{ o.taxonomy ? ` (${o.taxonomy})` : "" }} — Directory parent
              {{ formatHierarchyParent(o.directory_parent_name, o.directory_parent_id) }}; website parent
              {{ formatHierarchyParent(o.wordpress_parent_name, o.wordpress_parent_id) }}
            </li>
          </ul>
        </div>
        <div v-if="(driftReport.assignment_mismatches?.length ?? 0) > 0" class="drift-section">
          <h4>Role mismatches</h4>
          <ul>
            <li v-for="row in driftReport.assignment_mismatches" :key="row.person_id">
              <button type="button" class="linkish" @click="selectedPersonId = row.person_id">{{ row.person_name || row.person_id }}</button>
              <span v-if="row.missing_in_wp.length > 0"> missing on website: {{ row.missing_in_wp.map((o) => o.name).join(", ") }}</span>
              <span v-if="row.extra_in_wp.length > 0"> extra on website: {{ row.extra_in_wp.map((o) => o.name).join(", ") }}</span>
            </li>
          </ul>
        </div>
      </div>
      <p v-if="syncNotice" :class="syncNotice.kind === 'ok' ? 'success-msg' : 'error-msg'">{{ syncNotice.text }}</p>
      <p v-if="loading" class="muted">Loading organizations…</p>
      <p v-if="err" class="error-msg">{{ err }}</p>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Phone</th>
              <th>{{ selectedOrgId ? "Title (assignment)" : "Roles" }}</th>
              <th class="col-show-directory" title="Include this person on the public website and in print. Off drafts their WordPress person post.">
                Show in directory
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="p in people"
              :key="p.assignment_id ?? p.id"
              :class="{ 'row-active': p.id === selectedPersonId }"
              tabindex="0"
              role="button"
              @click="selectPersonRow(p)"
              @keydown.enter.space.prevent="selectPersonRow(p)"
            >
              <td>{{ p.full_name ?? "—" }}</td>
              <td>{{ p.email_public ?? "—" }}</td>
              <td>{{ formatPublicPhone(p.phone_public, p.phone_public_ext) }}</td>
              <td>
                <template v-if="selectedOrgId">{{ p.assignment_job_title ?? "—" }}</template>
                <template v-else-if="p.assignment_count">{{ p.assignment_summary ?? `${p.assignment_count} role${p.assignment_count === 1 ? "" : "s"}` }}</template>
                <em v-else class="muted">Unassigned</em>
              </td>
              <td class="td-show-directory" @click.stop>
                <input
                  type="checkbox"
                  class="table-checkbox"
                  :checked="!!p.show_in_directory"
                  :disabled="showInDirBusyId === p.id"
                  :aria-label="`Show ${p.full_name ?? 'this person'} in directory`"
                  @change.stop="patchShowInDirectory(p.id, ($event.target as HTMLInputElement).checked)"
                  @click.stop
                  @keydown.space.stop
                  @keydown.enter.stop
                />
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="people.length === 0 && !loading" class="muted empty-hint">
          {{ selectedOrgId === null && unassignedOnly ? "No people are unassigned to a role." : "No people match this view." }}
        </p>
      </div>
    </section>

    <OrgPanel
      v-if="orgEditorOpen && selectedOrgId"
      :org-id="selectedOrgId"
      @close="orgEditorOpen = false"
      @saved="loadOrgs()"
      @roles-mutated="loadPeople()"
    />
    <PersonPanel
      v-if="selectedPersonId"
      :person-id="selectedPersonId"
      @close="selectedPersonId = null"
      @saved="loadPeople()"
      @archived="selectedPersonId = null; loadPeople()"
    />
  </div>
</template>
