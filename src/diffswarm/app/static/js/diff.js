import { createApp, ref } from "vue";

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
      hunks,
    };
  },
  template: "#app",
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

const $APP = document.getElementById("root");
const { diffId: DIFF_ID } = $APP.dataset;
createApp(App).provide("diffId", DIFF_ID).mount($APP);
