import { createRouter, createWebHistory } from "vue-router";
import LoginPage from "./pages/LoginPage.vue";
import Layout from "./components/Layout.vue";
import DirectoryPage from "./pages/DirectoryPage.vue";
import ActivityPage from "./pages/ActivityPage.vue";
import PrintDirectoryPage from "./pages/PrintDirectoryPage.vue";
import PermissionsPage from "./pages/PermissionsPage.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: LoginPage },
    {
      path: "/",
      component: Layout,
      children: [
        { path: "", component: DirectoryPage },
        { path: "activity", component: ActivityPage },
        { path: "print-directory", component: PrintDirectoryPage },
        { path: "permissions", component: PermissionsPage },
      ],
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});

export default router;
