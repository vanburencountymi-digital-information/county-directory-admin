<script setup lang="ts">
import type { PrintDepartment } from "../api";

defineProps<{ departments: PrintDepartment[]; editionYear: number }>();

function groups(departments: PrintDepartment[]) {
  const out: { label: string | null; items: PrintDepartment[] }[] = [];
  for (const dept of departments) {
    const last = out[out.length - 1];
    if (last && last.label === dept.parent_group) last.items.push(dept);
    else out.push({ label: dept.parent_group, items: [dept] });
  }
  return out;
}
</script>

<template>
  <div class="print-document">
    <header class="print-header">
      <span>Van Buren County - Staff Directory</span>
      <span>{{ editionYear }}</span>
    </header>
    <main class="print-columns">
      <div v-for="group in groups(departments)" :key="group.label ?? '__ungrouped__'" class="print-group">
        <h2 v-if="group.label" class="print-group-title">{{ group.label }}</h2>
        <section v-for="department in group.items" :key="department.department" class="print-department">
          <h3 class="print-department-title">{{ department.department }}</h3>
          <div v-if="department.address || department.phone || department.email" class="print-dept-contact">
            <div v-if="department.address" class="print-dept-contact-line">{{ department.address }}</div>
            <div v-if="department.phone" class="print-dept-contact-line">{{ department.phone }}</div>
            <div v-if="department.email" class="print-dept-contact-line">{{ department.email }}</div>
          </div>
          <div class="print-entry-list">
            <article
              v-for="(entry, index) in department.entries"
              :key="`${department.department}-${entry.name}-${index}`"
              class="print-entry"
            >
              <div class="print-entry-name">{{ entry.name }}</div>
              <div v-if="entry.title" class="print-entry-line">{{ entry.title }}</div>
              <div v-if="entry.phone" class="print-entry-line">{{ entry.phone }}</div>
              <div v-if="entry.email" class="print-entry-line">{{ entry.email }}</div>
            </article>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>
