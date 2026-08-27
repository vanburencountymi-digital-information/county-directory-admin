declare module "pagedjs" {
  export class Previewer {
    preview(source: HTMLElement, stylesheets: string[], target: HTMLElement): Promise<unknown>;
  }
}

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<object, object, unknown>;
  export default component;
}
