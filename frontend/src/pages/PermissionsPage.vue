<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import {
  fetchCaps,
  fetchMe,
  fetchPersonCaps,
  grantPersonCap,
  revokePersonCap,
  searchPeopleForPermissions,
  type Cap,
  type Me,
  type PersonCap,
  type PersonSearchResult,
} from "../api";

const me = ref<Me | null>(null);
const caps = ref<Cap[]>([]);
const query = ref("");
const results = ref<PersonSearchResult[]>([]);
const searchBusy = ref(false);
const searchErr = ref<string | null>(null);
const selectedPerson = ref<PersonSearchResult | null>(null);
const personCaps = ref<PersonCap[]>([]);
const capsBusy = ref(false);
const capsErr = ref<string | null>(null);
const toggleBusyKey = ref<string | null>(null);

function personLabel(p: PersonSearchResult) {
  return p.full_name || [p.name_first, p.name_last].filter(Boolean).join(" ") || p.email_public || p.id;
}

onMounted(async () => {
  const r = await fetchMe();
  me.value = r.state === "ok" ? r.me : null;
  if (me.value?.permissions_admin) {
    try {
      caps.value = await fetchCaps();
    } catch (e) {
      searchErr.value = e instanceof Error ? e.message : "Failed to load caps";
    }
  }
});

let searchTimer: ReturnType<typeof setTimeout> | undefined;
watch(query, (q) => {
  if (searchTimer) clearTimeout(searchTimer);
  const trimmed = q.trim();
  if (trimmed.length < 2) {
    results.value = [];
    searchBusy.value = false;
    return;
  }
  searchBusy.value = true;
  searchTimer = setTimeout(() => {
    searchPeopleForPermissions(trimmed)
      .then((items) => {
        results.value = items;
      })
      .catch((e) => {
        searchErr.value = e instanceof Error ? e.message : "Search failed";
      })
      .finally(() => {
        searchBusy.value = false;
      });
  }, 250);
});

function loadPersonCaps(person: PersonSearchResult) {
  selectedPerson.value = person;
  capsBusy.value = true;
  fetchPersonCaps(person.id)
    .then((items) => {
      personCaps.value = items;
    })
    .catch((e) => {
      capsErr.value = e instanceof Error ? e.message : "Failed to load caps";
    })
    .finally(() => {
      capsBusy.value = false;
    });
}

async function toggleCap(cap: Cap, granted: boolean) {
  if (!selectedPerson.value) return;
  toggleBusyKey.value = cap.cap_key;
  try {
    if (granted) await revokePersonCap(selectedPerson.value.id, cap.cap_key);
    else await grantPersonCap(selectedPerson.value.id, cap.cap_key);
    personCaps.value = await fetchPersonCaps(selectedPerson.value.id);
  } catch (e) {
    capsErr.value = e instanceof Error ? e.message : "Update failed";
  } finally {
    toggleBusyKey.value = null;
  }
}

const grantedKeys = () => new Set(personCaps.value.map((c) => c.cap_key));
</script>

<template>
  <div class="permissions-page">
    <h2>Permissions</h2>
    <p v-if="me && !me.permissions_admin" class="muted">
      Your account does not have permission to manage capabilities.
    </p>
    <template v-else>
      <p class="muted">Search for a person to grant Directory editor or Permissions admin (creates a User if needed).</p>
      <input v-model="query" class="field-input" type="text" placeholder="Search by name or email…" />
      <p v-if="searchErr" class="error-msg">{{ searchErr }}</p>
      <div v-if="query.trim().length >= 2" class="table-wrap">
        <table class="data-table compact">
          <thead>
            <tr><th>Name</th><th>Email</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="p in results" :key="p.id">
              <td>{{ personLabel(p) }}</td>
              <td>{{ p.email_public }}</td>
              <td><button type="button" class="btn small" @click="loadPersonCaps(p)">Manage</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="selectedPerson" class="panel">
        <h3>{{ personLabel(selectedPerson) }}</h3>
        <p v-if="capsErr" class="error-msg">{{ capsErr }}</p>
        <table class="data-table compact">
          <tbody>
            <tr v-for="cap in caps" :key="cap.cap_key">
              <td>{{ cap.cap_label }}</td>
              <td class="muted">{{ cap.description }}</td>
              <td>
                <button
                  type="button"
                  :class="grantedKeys().has(cap.cap_key) ? 'btn small danger' : 'btn small primary'"
                  :disabled="toggleBusyKey === cap.cap_key"
                  @click="toggleCap(cap, grantedKeys().has(cap.cap_key))"
                >
                  {{ grantedKeys().has(cap.cap_key) ? "Revoke" : "Grant" }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
