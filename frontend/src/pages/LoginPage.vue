<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { apiPost, fetchMe } from "../api";

const email = ref("");
const sent = ref(false);
const err = ref<string | null>(null);
const checking = ref(true);
const loggedIn = ref(false);
const noAccess = ref(false);
const router = useRouter();

onMounted(async () => {
  try {
    const r = await fetchMe();
    if (r.state === "ok") {
      loggedIn.value = true;
      router.replace("/");
      return;
    }
    if (r.state === "forbidden") noAccess.value = true;
  } finally {
    checking.value = false;
  }
});

async function submit(e: Event) {
  e.preventDefault();
  err.value = null;
  try {
    await apiPost("/api/auth/request-otp", { email: email.value });
    sent.value = true;
  } catch (ex) {
    err.value = ex instanceof Error ? ex.message : "Request failed";
  }
}
</script>

<template>
  <div class="login-page">
    <p v-if="checking">Loading…</p>
    <div v-else-if="loggedIn" class="login-card">
      <p>Signed in. <a href="/">Continue</a></p>
    </div>
    <div v-else-if="noAccess" class="login-card">
      <h1>No access</h1>
      <p class="muted">
        You are signed in, but your account does not have permission to use Directory Admin.
      </p>
    </div>
    <div v-else class="login-card">
      <h1>Sign in</h1>
      <p class="muted">
        Previous Directory Admin sessions ended when this app moved to Django. Enter the work
        email listed in the directory for a one-time sign-in link.
      </p>
      <p v-if="sent" class="success-msg">
        If that email is on file, you will receive a link shortly.
      </p>
      <form v-else @submit="submit">
        <label class="field-label" for="email">Email</label>
        <input id="email" v-model="email" type="email" autocomplete="email" required class="field-input" />
        <p v-if="err" class="error-msg">{{ err }}</p>
        <button type="submit" class="btn primary">Send login link</button>
      </form>
    </div>
  </div>
</template>
