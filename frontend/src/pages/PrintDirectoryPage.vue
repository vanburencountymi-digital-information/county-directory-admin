<script setup lang="ts">
import { nextTick, ref } from "vue";
import { fetchPrintDirectory, type PrintDepartment } from "../api";
import DirectoryPrintTemplate from "../components/DirectoryPrintTemplate.vue";
import "../styles/print-directory.css";

const departments = ref<PrintDepartment[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const rendered = ref(false);
const sourceRef = ref<HTMLElement | null>(null);
const previewRef = ref<HTMLElement | null>(null);
const editionYear = new Date().getFullYear();

function printPreview() {
  window.print();
}

async function onPreviewClick() {
  loading.value = true;
  error.value = null;
  rendered.value = false;
  try {
    departments.value = await fetchPrintDirectory();
    await nextTick();
    if (sourceRef.value && previewRef.value) {
      previewRef.value.innerHTML = "";
      const { Previewer } = await import("pagedjs");
      await new Previewer().preview(sourceRef.value, [], previewRef.value);
      rendered.value = departments.value.length > 0;
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Failed to load print directory preview.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <section class="print-directory-page">
    <div class="print-directory-toolbar">
      <div>
        <h2>Print Directory</h2>
        <p class="muted">Generate a paginated preview, then print or Save as PDF.</p>
      </div>
      <div class="print-directory-actions">
        <button type="button" class="btn primary" :disabled="loading" @click="onPreviewClick">
          {{ loading ? "Loading preview..." : "Preview Directory" }}
        </button>
        <button type="button" class="btn ghost" :disabled="loading || !rendered" @click="printPreview">
          Print
        </button>
      </div>
    </div>
    <p v-if="error" class="error-msg">{{ error }}</p>
    <div class="print-preview-frame">
      <div class="print-preview-output" ref="previewRef" />
    </div>
    <div class="print-source" ref="sourceRef">
      <DirectoryPrintTemplate :departments="departments" :edition-year="editionYear" />
    </div>
  </section>
</template>
