import { createApp, inject, ref } from "vue";
import * as Y from "yjs";
import { WebsocketProvider } from "y-websocket";

const Test = {
  template: "#my-template-element",
};

const Hunk = {
  template: "#hunk-template",
  props: {
    filename: String,
    hunkHeader: String,
    changesSummary: String,
    lineCount: Number,
  },
};

const App = {
  components: {
    Test,
    Hunk,
  },
  setup() {
    const diffId = inject("diffId");
    const yWebsocketEndpoint = inject("yWebsocketEndpoint");
    const doc = new Y.Doc();
    new WebsocketProvider(yWebsocketEndpoint, diffId, doc);
    const reactiveArray = ref([]);
    const arr = doc.getArray("my-array");
    arr.observe(() => (reactiveArray.value = arr.toArray()));
    const message = ref("Hello Vue!");

    const hunks = ref([
      {
        filename: "src/components/Button.vue",
        hunkHeader: "@@ -12,7 +12,8 @@",
        changesSummary: "Added new prop validation",
        lineCount: 15,
      },
      {
        filename: "src/utils/helpers.js",
        hunkHeader: "@@ -45,3 +45,12 @@",
        changesSummary: "Added utility function",
        lineCount: 9,
      },
      {
        filename: "README.md",
        hunkHeader: "@@ -1,4 +1,6 @@",
        changesSummary: "Updated documentation",
        lineCount: 8,
      },
    ]);

    return {
      message,
      doc,
      reactiveArray,
      hunks,
    };
  },
  template: "#my-template-element",
  methods: {
    test() {
      const yarray = this.doc.getArray("my-array");
      yarray.push([1]);
    },
  },
};

/**
 * set up and mount the app
 */

const $APP = document.getElementById("app");
const { diffId: DIFF_ID, yWebsocketEndpoint: Y_WEBSOCKET_ENDPOINT } =
  $APP.dataset;

createApp(App)
  .provide("diffId", DIFF_ID)
  .provide("yWebsocketEndpoint", Y_WEBSOCKET_ENDPOINT)
  .mount($APP);
