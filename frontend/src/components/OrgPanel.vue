<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  apiDelete,
  apiGet,
  apiPatch,
  apiPost,
  formatPublicPhone,
  type Org,
  type OrgAssignment,
  type UnassignedPersonRow,
} from "../api";

type OrgDetail = {
  id: string;
  name: string | null;
  org_type: string | null;
  slug: string | null;
  parent_id: string | null;
  public_email: string | null;
  phone: string | null;
  hours_text: string | null;
  website_url: string | null;
  address_mailing: string | null;
  address_physical: string | null;
  additional_information: string | null;
  fax: string | null;
};

const EDIT_KEYS = [
  "name",
  "org_type",
  "parent_id",
  "public_email",
  "phone",
  "hours_text",
  "website_url",
  "address_mailing",
  "address_physical",
  "additional_information",
  "fax",
] as const;

const ORG_TYPE_OPTIONS = [
  { value: "department", label: "Department / Office" },
  { value: "board", label: "Board / Committee / Commission" },
  { value: "local_unit", label: "Local Unit (City / Township / Village)" },
  { value: "county", label: "County" },
  { value: "external", label: "External Organization" },
] as const;

const BOARD_LIKE_ORG_TYPES = new Set(["board", "commission", "committee", "authority", "task_force"]);

function hierarchyFamily(orgType: string | null | undefined): "board" | "department" {
  const t = (orgType ?? "").trim().toLowerCase();
  return BOARD_LIKE_ORG_TYPES.has(t) ? "board" : "department";
}

function descendantIds(orgId: string, orgs: Org[]): Set<string> {
  const childrenByParent = new Map<string, string[]>();
  for (const o of orgs) {
    if (!o.parent_id) continue;
    const list = childrenByParent.get(o.parent_id) ?? [];
    list.push(o.id);
    childrenByParent.set(o.parent_id, list);
  }
  const out = new Set<string>();
  const stack = [orgId];
  while (stack.length) {
    const id = stack.pop()!;
    if (out.has(id)) continue;
    out.add(id);
    for (const child of childrenByParent.get(id) ?? []) stack.push(child);
  }
  return out;
}

function personLookupLabel(p: UnassignedPersonRow): string {
  const name = p.full_name?.trim() || "—";
  const phone = formatPublicPhone(p.phone_public, p.phone_public_ext);
  const bits = [p.email_public?.trim(), phone === "—" ? "" : phone].filter(Boolean);
  return bits.length ? `${name} (${bits.join(", ")})` : name;
}

type OrgEditForm = Partial<Record<(typeof EDIT_KEYS)[number], string | null>>;

const props = withDefaults(
  defineProps<{
    orgId: string;
    initialTab?: "details" | "roles";
  }>(),
  { initialTab: "details" },
);

const emit = defineEmits<{
  close: [];
  saved: [];
  rolesMutated: [];
}>();

const tab = ref<"details" | "roles">(props.initialTab);
const data = ref<OrgDetail | null>(null);
const form = ref<OrgEditForm>({});
const msg = ref<string | null>(null);
const err = ref<string | null>(null);
const saving = ref(false);
const parentOptions = ref<Org[]>([]);
const assignments = ref<OrgAssignment[]>([]);
const assignsLoading = ref(false);
const assignsErr = ref<string | null>(null);
const editingId = ref<string | null>(null);
const editForm = ref({ job_title: "", status: "" });
const editBusy = ref(false);
const confirmDelete = ref<string | null>(null);
const deleteBusy = ref(false);
const addingRole = ref(false);
const newRoleForm = ref({ job_title: "", status: "" });
const addBusy = ref(false);
const assignPickerAssignmentId = ref<string | null>(null);
const assignSearch = ref("");
const assignDebounced = ref("");
const unassignedPeople = ref<UnassignedPersonRow[]>([]);
const unassignedTotal = ref(0);
const unassignedLoading = ref(false);
const selectedAssignPersonId = ref("");
const assignBusy = ref(false);
const shouldCloseOnClick = ref(false);
const quickAddOpen = ref(false);
const quickAddForm = ref({ name_first: "", name_last: "", email_public: "", show_in_directory: false });
const quickAddBusy = ref(false);
const quickAddErr = ref<string | null>(null);

watch(assignSearch, (v, _old, onCleanup) => {
  const t = setTimeout(() => {
    assignDebounced.value = v.trim();
  }, 300);
  onCleanup(() => clearTimeout(t));
});

watch(
  [assignPickerAssignmentId, assignDebounced, () => props.orgId, tab],
  (_n, _o, onCleanup) => {
    if (!assignPickerAssignmentId.value || tab.value !== "roles") return;
    let cancelled = false;
    unassignedLoading.value = true;
    const q = assignDebounced.value ? `?q=${encodeURIComponent(assignDebounced.value)}` : "";
    apiGet<{ items: UnassignedPersonRow[]; total: number }>(`/api/orgs/${props.orgId}/people/unassigned${q}`)
      .then((r) => {
        if (!cancelled) {
          unassignedPeople.value = r.items;
          unassignedTotal.value = typeof r.total === "number" ? r.total : r.items.length;
        }
      })
      .catch((e) => {
        if (!cancelled) assignsErr.value = e instanceof Error ? e.message : String(e);
      })
      .finally(() => {
        if (!cancelled) unassignedLoading.value = false;
      });
    onCleanup(() => {
      cancelled = true;
    });
  },
);

watch(unassignedPeople, (people) => {
  if (!assignPickerAssignmentId.value) return;
  if (selectedAssignPersonId.value && people.some((p) => p.id === selectedAssignPersonId.value)) return;
  selectedAssignPersonId.value = people[0]?.id ?? "";
});

watch(
  () => props.orgId,
  () => {
    assignPickerAssignmentId.value = null;
    assignSearch.value = "";
    assignDebounced.value = "";
    msg.value = null;
    err.value = null;
    apiGet<OrgDetail>(`/api/orgs/${props.orgId}`)
      .then((o) => {
        data.value = o;
        const next: OrgEditForm = {};
        for (const k of EDIT_KEYS) next[k] = o[k] ?? null;
        form.value = next;
      })
      .catch((e) => {
        err.value = String(e);
      });
    apiGet<{ items: Org[] }>("/api/orgs")
      .then((r) => {
        parentOptions.value = r.items ?? [];
      })
      .catch(() => {
        parentOptions.value = [];
      });
  },
  { immediate: true },
);

watch(tab, (t) => {
  if (t !== "roles") {
    assignPickerAssignmentId.value = null;
    assignSearch.value = "";
  }
});

watch(assignPickerAssignmentId, (id) => {
  if (!id) {
    quickAddOpen.value = false;
    quickAddErr.value = null;
  }
});

const parentSelectOptions = computed(() => {
  const family = hierarchyFamily(form.value.org_type ?? data.value?.org_type);
  const blocked = descendantIds(props.orgId, parentOptions.value);
  return parentOptions.value
    .filter((o) => hierarchyFamily(o.org_type) === family && !blocked.has(o.id))
    .slice()
    .sort((a, b) => (a.name || "").localeCompare(b.name || "", undefined, { sensitivity: "base" }));
});

const assignQueryPending = computed(() => assignSearch.value.trim() !== assignDebounced.value);

function loadAssignments() {
  assignsLoading.value = true;
  assignsErr.value = null;
  apiGet<{ items: OrgAssignment[] }>(`/api/orgs/${props.orgId}/assignments`)
    .then((r) => {
      assignments.value = r.items;
    })
    .catch((e) => {
      assignsErr.value = e instanceof Error ? e.message : String(e);
    })
    .finally(() => {
      assignsLoading.value = false;
    });
}

watch([tab, () => props.orgId], () => {
  if (tab.value === "roles") loadAssignments();
});

async function saveDetails() {
  if (!data.value) return;
  saving.value = true;
  err.value = null;
  msg.value = null;
  try {
    const body: Record<string, unknown> = {};
    for (const k of EDIT_KEYS) {
      if (form.value[k] !== data.value[k]) body[k] = form.value[k];
    }
    if (Object.keys(body).length === 0) {
      msg.value = "No changes to save.";
      saving.value = false;
      return;
    }
    await apiPatch(`/api/orgs/${props.orgId}`, body);
    msg.value = "Saved. You can undo from Activity.";
    emit("saved");
    const fresh = await apiGet<OrgDetail>(`/api/orgs/${props.orgId}`);
    data.value = fresh;
    const next: OrgEditForm = {};
    for (const k of EDIT_KEYS) next[k] = fresh[k] ?? null;
    form.value = next;
  } catch (e) {
    err.value = e instanceof Error ? e.message : "Save failed";
  } finally {
    saving.value = false;
  }
}

function startEdit(a: OrgAssignment) {
  editingId.value = a.id;
  editForm.value = { job_title: a.job_title ?? "", status: a.status ?? "" };
  confirmDelete.value = null;
  assignsErr.value = null;
}

async function saveEdit(assignmentId: string) {
  editBusy.value = true;
  assignsErr.value = null;
  try {
    await apiPatch(`/api/assignments/${assignmentId}`, {
      job_title: editForm.value.job_title || null,
      status: editForm.value.status || null,
    });
    editingId.value = null;
    loadAssignments();
  } catch (e) {
    assignsErr.value = e instanceof Error ? e.message : "Save failed";
  } finally {
    editBusy.value = false;
  }
}

async function doDelete(assignmentId: string) {
  deleteBusy.value = true;
  assignsErr.value = null;
  try {
    await apiDelete(`/api/assignments/${assignmentId}`);
    confirmDelete.value = null;
    loadAssignments();
  } catch (e) {
    assignsErr.value = e instanceof Error ? e.message : "Delete failed";
  } finally {
    deleteBusy.value = false;
  }
}

async function doAddRole() {
  addBusy.value = true;
  assignsErr.value = null;
  try {
    await apiPost(`/api/orgs/${props.orgId}/assignments`, {
      job_title: newRoleForm.value.job_title || null,
      status: newRoleForm.value.status || null,
    });
    addingRole.value = false;
    newRoleForm.value = { job_title: "", status: "" };
    loadAssignments();
  } catch (e) {
    assignsErr.value = e instanceof Error ? e.message : "Failed to create role";
  } finally {
    addBusy.value = false;
  }
}

async function doAssignPersonToRole() {
  if (!assignPickerAssignmentId.value || !selectedAssignPersonId.value) return;
  assignBusy.value = true;
  assignsErr.value = null;
  try {
    await apiPost(`/api/assignments/${assignPickerAssignmentId.value}/person`, {
      person_id: selectedAssignPersonId.value,
    });
    assignPickerAssignmentId.value = null;
    assignSearch.value = "";
    assignDebounced.value = "";
    loadAssignments();
    emit("rolesMutated");
  } catch (e) {
    assignsErr.value = e instanceof Error ? e.message : "Assign failed";
  } finally {
    assignBusy.value = false;
  }
}

function openQuickAddPerson() {
  quickAddErr.value = null;
  const q = assignDebounced.value;
  const looksLikeEmail = q.includes("@") && !/\s/.test(q);
  quickAddForm.value = {
    name_first: "",
    name_last: "",
    email_public: looksLikeEmail ? q : "",
    show_in_directory: false,
  };
  quickAddOpen.value = true;
}

function closeQuickAddPerson() {
  quickAddOpen.value = false;
  quickAddErr.value = null;
}

async function createPersonAndAssignToOpenRole() {
  if (!assignPickerAssignmentId.value) return;
  const nf = quickAddForm.value.name_first.trim();
  const nl = quickAddForm.value.name_last.trim();
  const em = quickAddForm.value.email_public.trim();
  if (!nf && !nl && !em) {
    quickAddErr.value = "Enter at least a first name, last name, or email.";
    return;
  }
  quickAddBusy.value = true;
  quickAddErr.value = null;
  assignsErr.value = null;
  try {
    const created = await apiPost<{ ok?: boolean; person?: { id: string } }>("/api/people", {
      name_first: nf || null,
      name_last: nl || null,
      email_public: em || null,
      show_in_directory: quickAddForm.value.show_in_directory,
    });
    const personId = created.person?.id;
    if (!personId) throw new Error("Person was created but no id was returned.");
    await apiPost(`/api/assignments/${assignPickerAssignmentId.value}/person`, { person_id: personId });
    closeQuickAddPerson();
    quickAddForm.value = { name_first: "", name_last: "", email_public: "", show_in_directory: false };
    assignPickerAssignmentId.value = null;
    assignSearch.value = "";
    assignDebounced.value = "";
    loadAssignments();
    emit("rolesMutated");
  } catch (e) {
    quickAddErr.value = e instanceof Error ? e.message : "Could not create or assign person.";
  } finally {
    quickAddBusy.value = false;
  }
}

function setFormField(key: (typeof EDIT_KEYS)[number], value: string | null) {
  form.value = { ...form.value, [key]: value };
}
</script>

<template>
  <div
    class="drawer-backdrop"
    role="presentation"
    @mousedown="shouldCloseOnClick = ($event.target === $event.currentTarget)"
    @click="shouldCloseOnClick && emit('close')"
  >
    <div class="drawer" @mousedown="shouldCloseOnClick = false">
      <div v-if="!data && !err"><p>Loading…</p></div>
      <template v-else>
        <div class="drawer-head">
          <h3>Edit organization</h3>
          <button type="button" class="btn ghost" @click="emit('close')">Close</button>
        </div>
        <div class="drawer-tabs">
          <button type="button" :class="tab === 'details' ? 'drawer-tab active' : 'drawer-tab'" @click="tab = 'details'">Details</button>
          <button type="button" :class="tab === 'roles' ? 'drawer-tab active' : 'drawer-tab'" @click="tab = 'roles'">Roles</button>
        </div>

        <template v-if="tab === 'details'">
          <p v-if="err" class="error-msg">{{ err }}</p>
          <p v-if="msg" class="success-msg">{{ msg }}</p>
          <template v-if="data">
            <p v-if="data.slug" class="muted meta-line">{{ data.slug }}</p>
            <div class="form-grid form-grid--twocol">
              <label>Name
                <input class="field-input" :value="form.name ?? ''" @input="setFormField('name', ($event.target as HTMLInputElement).value || null)" />
              </label>
              <label>Type
                <select class="field-input" :value="form.org_type ?? ''" @change="setFormField('org_type', ($event.target as HTMLSelectElement).value || null)">
                  <option v-if="form.org_type && !ORG_TYPE_OPTIONS.some((o) => o.value === form.org_type)" :value="form.org_type">{{ form.org_type }}</option>
                  <option v-for="o in ORG_TYPE_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
                </select>
              </label>
              <label class="span-2">Parent organization
                <select class="field-input" :value="form.parent_id ?? ''" @change="setFormField('parent_id', ($event.target as HTMLSelectElement).value || null)">
                  <option value="">None (top-level)</option>
                  <option v-if="form.parent_id && !parentSelectOptions.some((o) => o.id === form.parent_id)" :value="form.parent_id">
                    Current parent (incompatible with selected type — choose another or None)
                  </option>
                  <option v-for="o in parentSelectOptions" :key="o.id" :value="o.id">{{ o.name }}</option>
                </select>
                <span class="muted small">Controls WordPress department/board term hierarchy after sync. Parent must be the same family (department vs board).</span>
              </label>
              <label>Public email
                <input class="field-input" type="email" :value="form.public_email ?? ''" @input="setFormField('public_email', ($event.target as HTMLInputElement).value || null)" />
              </label>
              <label>Phone
                <input class="field-input" :value="form.phone ?? ''" @input="setFormField('phone', ($event.target as HTMLInputElement).value || null)" />
              </label>
              <label>Fax
                <input class="field-input" :value="form.fax ?? ''" @input="setFormField('fax', ($event.target as HTMLInputElement).value || null)" />
              </label>
              <label>Website URL
                <input class="field-input" type="url" placeholder="https://…" :value="form.website_url ?? ''" @input="setFormField('website_url', ($event.target as HTMLInputElement).value || null)" />
              </label>
              <label class="span-2">Hours
                <textarea class="field-input textarea" rows="3" :value="form.hours_text ?? ''" @input="setFormField('hours_text', ($event.target as HTMLTextAreaElement).value || null)" />
              </label>
              <label class="span-2">Mailing address
                <textarea class="field-input textarea" rows="3" :value="form.address_mailing ?? ''" @input="setFormField('address_mailing', ($event.target as HTMLTextAreaElement).value || null)" />
              </label>
              <label class="span-2">Physical address
                <textarea class="field-input textarea" rows="3" :value="form.address_physical ?? ''" @input="setFormField('address_physical', ($event.target as HTMLTextAreaElement).value || null)" />
              </label>
              <label class="span-2">Additional information
                <textarea class="field-input textarea" rows="4" :value="form.additional_information ?? ''" @input="setFormField('additional_information', ($event.target as HTMLTextAreaElement).value || null)" />
              </label>
            </div>
            <div class="drawer-actions">
              <button type="button" class="btn primary" :disabled="saving" @click="saveDetails">{{ saving ? "Saving…" : "Save changes" }}</button>
            </div>
          </template>
        </template>

        <div v-if="tab === 'roles'" class="roles-tab">
          <p v-if="assignsErr" class="error-msg">{{ assignsErr }}</p>
          <p v-if="assignsLoading" class="muted">Loading roles…</p>
          <template v-if="!assignsLoading">
            <ul class="assignment-list">
              <li v-if="assignments.length === 0"><p class="muted">No roles defined for this org.</p></li>
              <li v-for="a in assignments" :key="a.id" class="assignment-row">
                <div v-if="editingId === a.id" class="assignment-edit-form">
                  <input class="field-input assignment-edit-title-input" placeholder="Role name" v-model="editForm.job_title" />
                  <div class="assignment-edit-meta">
                    <input class="field-input assignment-edit-meta-input" placeholder="Status (optional)" v-model="editForm.status" />
                    <div class="assignment-actions">
                      <button type="button" class="btn primary small" :disabled="editBusy" @click="saveEdit(a.id)">{{ editBusy ? "Saving…" : "Save" }}</button>
                      <button type="button" class="btn ghost small" @click="editingId = null">Cancel</button>
                    </div>
                  </div>
                </div>
                <template v-else>
                  <div class="assignment-info">
                    <span class="assignment-title">
                      <template v-if="a.job_title">{{ a.job_title }}</template>
                      <em v-else class="muted">Untitled role</em>
                    </span>
                    <span v-if="a.status" class="muted small"> · {{ a.status }}</span>
                    <div class="assignment-person">
                      <span v-if="a.person_id">{{ a.person_full_name ?? a.person_email ?? "Assigned" }}</span>
                      <span v-else class="open-badge">Open position</span>
                    </div>
                  </div>
                  <div class="assignment-actions">
                    <button type="button" class="btn ghost small" @click="startEdit(a)">Edit</button>
                    <template v-if="!a.person_id">
                      <button
                        v-if="assignPickerAssignmentId === a.id"
                        type="button"
                        class="btn ghost small"
                        @click="assignPickerAssignmentId = null; assignSearch = ''"
                      >
                        Cancel assign
                      </button>
                      <button
                        v-else
                        type="button"
                        class="btn ghost small"
                        @click="assignPickerAssignmentId = a.id; assignSearch = ''; editingId = null; confirmDelete = null; addingRole = false"
                      >
                        Assign…
                      </button>
                      <template v-if="confirmDelete === a.id">
                        <span class="muted small">Delete?</span>
                        <button type="button" class="btn danger small" :disabled="deleteBusy" @click="doDelete(a.id)">Confirm</button>
                        <button type="button" class="btn ghost small" @click="confirmDelete = null">Cancel</button>
                      </template>
                      <button
                        v-else-if="assignPickerAssignmentId !== a.id"
                        type="button"
                        class="btn ghost small"
                        @click="confirmDelete = a.id; editingId = null"
                      >
                        Delete
                      </button>
                    </template>
                  </div>
                  <div v-if="!a.person_id && assignPickerAssignmentId === a.id" class="role-picker assign-role-picker">
                    <label class="assign-role-search-label">
                      Search people
                      <input type="search" class="field-input" placeholder="Name or email…" v-model="assignSearch" autocomplete="off" />
                    </label>
                    <p class="muted small assign-role-picker-hint">Only people with no role in this organization yet. Results update as you type.</p>
                    <p v-if="assignQueryPending" class="muted small">Waiting for your search…</p>
                    <p v-else-if="unassignedLoading" class="muted small">Loading…</p>
                    <template v-else>
                      <template v-if="unassignedPeople.length === 0">
                        <p class="muted small">{{ assignDebounced !== "" ? "No matches — try another name or email." : "No one is available to assign here." }}</p>
                        <div class="assign-role-add-new">
                          <button type="button" class="btn primary small" @click="openQuickAddPerson">Add new person…</button>
                        </div>
                      </template>
                      <template v-else>
                        <p v-if="unassignedTotal > unassignedPeople.length" class="muted small">
                          Showing {{ unassignedPeople.length }} of {{ unassignedTotal }}. Narrow the search to find someone not listed.
                        </p>
                        <p v-else-if="unassignedTotal > 12" class="muted small">{{ unassignedTotal }} people — use search if needed.</p>
                        <select class="field-input" v-model="selectedAssignPersonId">
                          <option v-for="p in unassignedPeople" :key="p.id" :value="p.id">{{ personLookupLabel(p) }}</option>
                        </select>
                        <div class="role-picker-actions">
                          <button type="button" class="btn primary small" :disabled="assignBusy || !selectedAssignPersonId" @click="doAssignPersonToRole">
                            {{ assignBusy ? "Assigning…" : "Assign to this role" }}
                          </button>
                        </div>
                        <div class="assign-role-add-new">
                          <p class="muted small assign-role-add-new-hint">Not the right person?</p>
                          <button type="button" class="btn ghost small" @click="openQuickAddPerson">Add new person…</button>
                        </div>
                      </template>
                    </template>
                  </div>
                </template>
              </li>
            </ul>
            <div v-if="addingRole" class="add-role-form">
              <h5>New role</h5>
              <input class="field-input assignment-edit-title-input" placeholder="Role name" v-model="newRoleForm.job_title" />
              <div class="assignment-edit-meta">
                <input class="field-input assignment-edit-meta-input" placeholder="Status (optional)" v-model="newRoleForm.status" />
                <div class="assignment-actions">
                  <button type="button" class="btn primary small" :disabled="addBusy" @click="doAddRole">{{ addBusy ? "Adding…" : "Add role" }}</button>
                  <button type="button" class="btn ghost small" @click="addingRole = false; newRoleForm = { job_title: '', status: '' }">Cancel</button>
                </div>
              </div>
            </div>
            <button v-else type="button" class="btn ghost small" @click="addingRole = true; editingId = null; confirmDelete = null">+ Add role</button>
          </template>
        </div>

        <div
          v-if="quickAddOpen && assignPickerAssignmentId"
          class="drawer-modal-overlay"
          role="presentation"
          @mousedown.stop="($event.target === $event.currentTarget) && closeQuickAddPerson()"
        >
          <div class="drawer-modal" role="dialog" aria-modal="true" aria-labelledby="quick-add-person-title" @mousedown.stop>
            <h4 id="quick-add-person-title">Add person and assign</h4>
            <p class="muted small">They will be created in the directory and assigned to this open role.</p>
            <p v-if="quickAddErr" class="error-msg">{{ quickAddErr }}</p>
            <div class="form-grid form-grid--twocol">
              <label>First name<input class="field-input" v-model="quickAddForm.name_first" autocomplete="given-name" /></label>
              <label>Last name<input class="field-input" v-model="quickAddForm.name_last" autocomplete="family-name" /></label>
              <label class="span-2">Email (optional)<input class="field-input" type="email" v-model="quickAddForm.email_public" autocomplete="email" /></label>
              <label class="checkbox-row span-2">
                <input type="checkbox" v-model="quickAddForm.show_in_directory" />
                Show in directory
              </label>
            </div>
            <div class="drawer-modal-actions">
              <button type="button" class="btn primary" :disabled="quickAddBusy" @click="createPersonAndAssignToOpenRole">
                {{ quickAddBusy ? "Saving…" : "Create and assign" }}
              </button>
              <button type="button" class="btn ghost" :disabled="quickAddBusy" @click="closeQuickAddPerson">Cancel</button>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
