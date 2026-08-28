<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { apiDelete, apiGet, apiPatch, apiPost, type OpenAssignment } from "../api";

type Assignment = {
  id: string;
  org_id: string | null;
  org_name: string | null;
  job_title: string | null;
  status: string | null;
};

type PersonDetail = {
  id: string;
  full_name: string | null;
  display_name: string | null;
  name_first: string | null;
  name_middle: string | null;
  name_last: string | null;
  name_suffix: string | null;
  email_public: string | null;
  phone_public: string | null;
  phone_public_ext: string | null;
  show_in_directory: boolean;
  employee_id: string | null;
  assignments: Assignment[];
};

const props = defineProps<{
  personId: string;
}>();

const emit = defineEmits<{
  close: [];
  saved: [];
  archived: [];
}>();

const data = ref<PersonDetail | null>(null);
const form = ref<Partial<PersonDetail>>({});
const msg = ref<string | null>(null);
const err = ref<string | null>(null);
const saving = ref(false);
const confirmUnlink = ref<string | null>(null);
const roleActionBusy = ref(false);
const roleErr = ref<string | null>(null);
const editingAssignmentId = ref<string | null>(null);
const editRoleForm = ref({ job_title: "", status: "" });
const editRoleBusy = ref(false);
const openRoles = ref<OpenAssignment[]>([]);
const pickerOpen = ref(false);
const selectedRoleId = ref("");
const confirmArchive = ref(false);
const archiveBusy = ref(false);
const shouldCloseOnClick = ref(false);
const syncBusy = ref(false);

function loadPerson() {
  msg.value = null;
  err.value = null;
  apiGet<PersonDetail>(`/api/people/${props.personId}`)
    .then((p) => {
      data.value = p;
      form.value = {
        display_name: p.display_name,
        name_first: p.name_first,
        name_middle: p.name_middle,
        name_last: p.name_last,
        name_suffix: p.name_suffix,
        email_public: p.email_public,
        phone_public: p.phone_public,
        phone_public_ext: p.phone_public_ext,
        show_in_directory: p.show_in_directory,
        employee_id: p.employee_id,
      };
    })
    .catch((e) => {
      err.value = String(e);
    });
}

watch(() => props.personId, loadPerson, { immediate: true });

const composedName = computed(() =>
  [form.value.name_first, form.value.name_middle, form.value.name_last, form.value.name_suffix]
    .map((p) => (p ?? "").trim())
    .filter(Boolean)
    .join(" "),
);

async function save() {
  if (!data.value) return;
  saving.value = true;
  err.value = null;
  msg.value = null;
  try {
    const body: Record<string, unknown> = {};
    const keys: (keyof PersonDetail)[] = [
      "display_name",
      "name_first",
      "name_middle",
      "name_last",
      "name_suffix",
      "email_public",
      "phone_public",
      "phone_public_ext",
      "show_in_directory",
      "employee_id",
    ];
    for (const k of keys) {
      if (form.value[k] !== data.value[k]) body[k] = form.value[k];
    }
    if (Object.keys(body).length === 0) {
      msg.value = "No changes to save.";
      saving.value = false;
      return;
    }
    await apiPatch(`/api/people/${props.personId}`, body);
    msg.value = "Saved. You can undo from Activity.";
    emit("saved");
    data.value = await apiGet<PersonDetail>(`/api/people/${props.personId}`);
  } catch (e) {
    err.value = e instanceof Error ? e.message : "Save failed";
  } finally {
    saving.value = false;
  }
}

async function forceSync() {
  syncBusy.value = true;
  err.value = null;
  msg.value = null;
  try {
    await apiPost(`/api/wordpress/people/${props.personId}/sync`);
    msg.value = "Pushed this person to the county website.";
  } catch (e) {
    err.value = e instanceof Error ? e.message : "WordPress push failed";
  } finally {
    syncBusy.value = false;
  }
}

async function doUnlink(assignmentId: string) {
  roleActionBusy.value = true;
  roleErr.value = null;
  try {
    await apiDelete(`/api/assignments/${assignmentId}/person`);
    data.value = await apiGet<PersonDetail>(`/api/people/${props.personId}`);
    confirmUnlink.value = null;
    emit("saved");
  } catch (e) {
    roleErr.value = e instanceof Error ? e.message : "Unlink failed";
  } finally {
    roleActionBusy.value = false;
  }
}

async function openRolePicker() {
  roleErr.value = null;
  try {
    const r = await apiGet<{ items: OpenAssignment[] }>("/api/assignments/open");
    openRoles.value = r.items;
    selectedRoleId.value = r.items[0]?.id ?? "";
    pickerOpen.value = true;
  } catch (e) {
    roleErr.value = e instanceof Error ? e.message : "Failed to load open roles";
  }
}

async function doAssignRole() {
  if (!selectedRoleId.value) return;
  roleActionBusy.value = true;
  roleErr.value = null;
  try {
    await apiPost(`/api/assignments/${selectedRoleId.value}/person`, { person_id: props.personId });
    data.value = await apiGet<PersonDetail>(`/api/people/${props.personId}`);
    pickerOpen.value = false;
    selectedRoleId.value = "";
    emit("saved");
  } catch (e) {
    roleErr.value = e instanceof Error ? e.message : "Failed to assign role";
  } finally {
    roleActionBusy.value = false;
  }
}

async function doArchive() {
  archiveBusy.value = true;
  err.value = null;
  try {
    await apiDelete(`/api/people/${props.personId}`);
    emit("archived");
    emit("close");
  } catch (e) {
    err.value = e instanceof Error ? e.message : "Archive failed";
    archiveBusy.value = false;
    confirmArchive.value = false;
  }
}

function startEditAssignment(a: Assignment) {
  editingAssignmentId.value = a.id;
  editRoleForm.value = { job_title: a.job_title ?? "", status: a.status ?? "" };
  confirmUnlink.value = null;
  pickerOpen.value = false;
  roleErr.value = null;
}

async function saveAssignment(assignmentId: string) {
  editRoleBusy.value = true;
  roleErr.value = null;
  try {
    await apiPatch(`/api/assignments/${assignmentId}`, {
      job_title: editRoleForm.value.job_title || null,
      status: editRoleForm.value.status || null,
    });
    data.value = await apiGet<PersonDetail>(`/api/people/${props.personId}`);
    editingAssignmentId.value = null;
    emit("saved");
  } catch (e) {
    roleErr.value = e instanceof Error ? e.message : "Failed to update role";
  } finally {
    editRoleBusy.value = false;
  }
}

function onBackdropMouseDown(e: MouseEvent) {
  shouldCloseOnClick.value = e.target === e.currentTarget;
}

function onBackdropClick() {
  if (shouldCloseOnClick.value) emit("close");
}
</script>

<template>
  <div
    class="drawer-backdrop"
    role="presentation"
    @mousedown="onBackdropMouseDown"
    @click="onBackdropClick"
  >
    <div class="drawer" @mousedown="shouldCloseOnClick = false">
      <div v-if="!data && !err">
        <p>Loading…</p>
      </div>
      <template v-else>
        <div class="drawer-head">
          <h3>Edit person</h3>
          <button type="button" class="btn ghost" @click="emit('close')">Close</button>
        </div>
        <p v-if="err" class="error-msg">{{ err }}</p>
        <p v-if="msg" class="success-msg">{{ msg }}</p>
        <template v-if="data">
          <div class="form-grid form-grid--twocol">
            <label>
              First
              <input class="field-input" :value="form.name_first ?? ''" @input="form.name_first = ($event.target as HTMLInputElement).value || null" />
            </label>
            <label>
              Middle
              <input class="field-input" :value="form.name_middle ?? ''" @input="form.name_middle = ($event.target as HTMLInputElement).value || null" />
            </label>
            <label>
              Last
              <input class="field-input" :value="form.name_last ?? ''" @input="form.name_last = ($event.target as HTMLInputElement).value || null" />
            </label>
            <label>
              Suffix
              <input class="field-input" :value="form.name_suffix ?? ''" @input="form.name_suffix = ($event.target as HTMLInputElement).value || null" />
            </label>
            <label class="span-2">
              Display name
              <input
                class="field-input"
                :placeholder="composedName || 'Uses first + middle + last + suffix when blank'"
                :value="form.display_name ?? ''"
                @input="form.display_name = ($event.target as HTMLInputElement).value || null"
              />
            </label>
            <label>
              Email (public)
              <input class="field-input" type="email" :value="form.email_public ?? ''" @input="form.email_public = ($event.target as HTMLInputElement).value || null" />
            </label>
            <label>
              Phone
              <input class="field-input" :value="form.phone_public ?? ''" @input="form.phone_public = ($event.target as HTMLInputElement).value || null" />
            </label>
            <label>
              Ext
              <input class="field-input" :value="form.phone_public_ext ?? ''" @input="form.phone_public_ext = ($event.target as HTMLInputElement).value || null" />
            </label>
            <label class="checkbox-row">
              <input type="checkbox" :checked="!!form.show_in_directory" @change="form.show_in_directory = ($event.target as HTMLInputElement).checked" />
              Show in directory
            </label>
            <label>
              Employee ID
              <input class="field-input" :value="form.employee_id ?? ''" @input="form.employee_id = ($event.target as HTMLInputElement).value || null" />
            </label>
          </div>

          <section class="assignments-box">
            <h4>Roles</h4>
            <p v-if="roleErr" class="error-msg">{{ roleErr }}</p>
            <p v-if="data.assignments.length === 0" class="muted">No roles assigned.</p>
            <ul class="assignment-list">
              <li v-for="a in data.assignments" :key="a.id" class="assignment-row">
                <div v-if="editingAssignmentId === a.id" class="assignment-edit-form">
                  <input
                    class="field-input assignment-edit-title-input"
                    placeholder="Role name"
                    :value="editRoleForm.job_title"
                    @input="editRoleForm.job_title = ($event.target as HTMLInputElement).value"
                  />
                  <div class="assignment-edit-meta">
                    <input
                      class="field-input assignment-edit-meta-input"
                      placeholder="Status (optional)"
                      :value="editRoleForm.status"
                      @input="editRoleForm.status = ($event.target as HTMLInputElement).value"
                    />
                    <div class="assignment-actions">
                      <button type="button" class="btn primary small" :disabled="editRoleBusy" @click="saveAssignment(a.id)">
                        {{ editRoleBusy ? "Saving…" : "Save" }}
                      </button>
                      <button type="button" class="btn ghost small" @click="editingAssignmentId = null">Cancel</button>
                    </div>
                  </div>
                </div>
                <template v-else>
                  <div class="assignment-info">
                    <strong>{{ a.org_name ?? "Unknown org" }}</strong>
                    {{ a.job_title ? ` — ${a.job_title}` : "" }}
                    <span v-if="a.status" class="muted"> ({{ a.status }})</span>
                  </div>
                  <div class="assignment-actions">
                    <template v-if="confirmUnlink === a.id">
                      <span class="muted small">Unlink?</span>
                      <button type="button" class="btn danger small" :disabled="roleActionBusy" @click="doUnlink(a.id)">Confirm</button>
                      <button type="button" class="btn ghost small" @click="confirmUnlink = null">Cancel</button>
                    </template>
                    <template v-else>
                      <button type="button" class="btn ghost small" @click="startEditAssignment(a)">Edit role</button>
                      <button
                        type="button"
                        class="btn ghost small"
                        @click="confirmUnlink = a.id; pickerOpen = false; editingAssignmentId = null"
                      >
                        Unlink
                      </button>
                    </template>
                  </div>
                </template>
              </li>
            </ul>

            <div v-if="pickerOpen" class="role-picker">
              <p v-if="openRoles.length === 0" class="muted small">No open roles available.</p>
              <template v-else>
                <select class="field-input" :value="selectedRoleId" @change="selectedRoleId = ($event.target as HTMLSelectElement).value">
                  <option v-for="r in openRoles" :key="r.id" :value="r.id">
                    {{ r.org_name ?? "Unknown org" }}{{ r.job_title ? ` — ${r.job_title}` : " — (untitled role)" }}
                  </option>
                </select>
                <div class="role-picker-actions">
                  <button type="button" class="btn primary small" :disabled="roleActionBusy || !selectedRoleId" @click="doAssignRole">
                    {{ roleActionBusy ? "Assigning…" : "Assign to role" }}
                  </button>
                  <button type="button" class="btn ghost small" @click="pickerOpen = false; roleErr = null">Cancel</button>
                </div>
              </template>
            </div>
            <button v-else type="button" class="btn ghost small" @click="confirmUnlink = null; openRolePicker()">
              + Assign to open role
            </button>
          </section>

          <div class="drawer-actions">
            <button type="button" class="btn primary" :disabled="saving" @click="save">
              {{ saving ? "Saving…" : "Save changes" }}
            </button>
            <button
              type="button"
              class="btn ghost"
              :disabled="syncBusy || saving"
              title="Push this person and their roles to the county website now, even if incremental sync skipped them"
              @click="forceSync"
            >
              {{ syncBusy ? "Pushing…" : "Push this person to website" }}
            </button>
          </div>

          <div class="drawer-danger-zone">
            <template v-if="confirmArchive">
              <span class="muted small">Archive this person and unlink all their roles?</span>
              <button type="button" class="btn danger small" :disabled="archiveBusy" @click="doArchive">
                {{ archiveBusy ? "Archiving…" : "Yes, archive" }}
              </button>
              <button type="button" class="btn ghost small" @click="confirmArchive = false">Cancel</button>
            </template>
            <button v-else type="button" class="btn ghost small danger-text" @click="confirmArchive = true">
              Archive person…
            </button>
          </div>
        </template>
      </template>
    </div>
  </div>
</template>
