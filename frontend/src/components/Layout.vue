<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { fetchMe, setActiveTenant, type Me } from "../api";

const me = ref<Me | null>(null);
const tenantBusy = ref(false);
const router = useRouter();

onMounted(async () => {
  const r = await fetchMe();
  if (r.state === "unauthorized") {
    router.replace("/login");
    return;
  }
  if (r.state === "forbidden") {
    router.replace("/login");
    return;
  }
  me.value = r.me;
});

function onTenantChange(event: Event) {
  const v = (event.target as HTMLSelectElement).value;
  if (!me.value || v === me.value.active_tenant_id) return;
  tenantBusy.value = true;
  setActiveTenant(v)
    .then(() => window.location.reload())
    .catch(() => {
      tenantBusy.value = false;
    });
}
</script>

<template>
  <div v-if="!me" class="loading-screen"><p>Loading…</p></div>
  <div v-else class="app-shell">
    <header class="top-bar">
      <div class="brand">
        <span class="brand-mark">DC</span>
        <div>
          <div class="brand-title">Directory Admin</div>
          <div class="brand-sub">
            {{ me.name ?? "Signed in" }}
            <template v-if="me.email"> · {{ me.email }}</template>
          </div>
          <label v-if="me.allowed_tenant_ids.length > 1" class="tenant-switch">
            <span class="tenant-switch-label">Data for</span>
            <select
              class="field-input tenant-select"
              :value="me.active_tenant_id"
              :disabled="tenantBusy"
              @change="onTenantChange"
            >
              <option v-for="id in me.allowed_tenant_ids" :key="id" :value="id">{{ id }}</option>
            </select>
          </label>
          <div v-else class="brand-sub muted tiny">Tenant: {{ me.active_tenant_id }}</div>
        </div>
      </div>
      <nav class="nav-tabs">
        <RouterLink to="/" class="nav-link" exact-active-class="active" active-class="">Directory</RouterLink>
        <RouterLink to="/activity" class="nav-link" active-class="active">Activity &amp; undo</RouterLink>
        <RouterLink to="/print-directory" class="nav-link" active-class="active">Print directory</RouterLink>
        <RouterLink v-if="me.permissions_admin" to="/permissions" class="nav-link" active-class="active">Permissions</RouterLink>
      </nav>
    </header>
    <main class="main-area">
      <router-view />
    </main>
  </div>
</template>
