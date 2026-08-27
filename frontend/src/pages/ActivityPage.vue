<script setup lang="ts">
import { onMounted, ref } from "vue";
import { apiGet, apiPost, type AuditItem } from "../api";

const items = ref<AuditItem[]>([]);
const err = ref<string | null>(null);
const busy = ref<number | null>(null);

function formatTs(ts: string) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

async function load() {
  err.value = null;
  try {
    const r = await apiGet<{ items: AuditItem[] }>("/api/audit?limit=100");
    items.value = r.items;
  } catch (e) {
    err.value = e instanceof Error ? e.message : "Load failed";
  }
}

async function revert(id: number) {
  busy.value = id;
  err.value = null;
  try {
    await apiPost(`/api/audit/${id}/revert`);
    await load();
  } catch (e) {
    err.value = e instanceof Error ? e.message : "Revert failed";
  } finally {
    busy.value = null;
  }
}

onMounted(load);
</script>

<template>
  <div class="activity-page">
    <div class="toolbar">
      <h2>Recent activity</h2>
      <button type="button" class="btn ghost" @click="load">Refresh</button>
    </div>
    <p class="muted">
      Edits you make in Directory are listed here. You can undo a change if nobody has edited the same record since.
    </p>
    <p v-if="err" class="error-msg">{{ err }}</p>
    <div class="table-wrap">
      <table class="data-table compact">
        <thead>
          <tr>
            <th>When</th>
            <th>Who</th>
            <th>Action</th>
            <th>Entity</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in items" :key="row.id">
            <td class="nowrap">{{ formatTs(row.ts) }}</td>
            <td>{{ row.actor }}</td>
            <td>{{ row.action }}</td>
            <td>
              {{ row.entity_type }}
              <span class="muted small-id">{{ row.entity_id }}</span>
            </td>
            <td>
              <button
                v-if="row.action === 'directory.mutation' && !(row.details as any)?.reverted && (row.details as any)?.op === 'update'"
                type="button"
                class="btn small danger"
                :disabled="busy === row.id"
                @click="revert(row.id)"
              >
                {{ busy === row.id ? "…" : "Undo" }}
              </button>
              <span v-if="(row.details as any)?.reverted" class="muted">Undone</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
