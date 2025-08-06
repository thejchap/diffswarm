import { createApp, inject } from "vue";

const FileHeader = {
  template: "#file-header",
  setup() {
    const diffId = inject("diffId");
    return {
      diffId,
    };
  },
};

const App = {
  components: {
    FileHeader,
  },
  template: "#app",
};

/**
 * set up and mount the app
 */

const $APP = document.getElementById("root");
const { diffId: DIFF_ID } = $APP.dataset;
createApp(App).provide("diffId", DIFF_ID).mount($APP);
