import { createApp } from "vue";
import * as Y from "yjs";
import { ref } from "vue";
import { WebsocketProvider } from "y-websocket";

const Test = {
  template: "#my-template-element",
};

const App = {
  components: {
    Test,
  },
  setup() {
    const diffId = document.querySelector("meta[name='diff-id']").content;
    const doc = new Y.Doc();
    const wsProvider = new WebsocketProvider(
      "ws://localhost:8000/ws",
      diffId,
      doc,
    );
    const reactiveArray = ref([]);
    const arr = doc.getArray("my-array");
    arr.observe((evt) => reactiveArray.value = arr.toArray())
    const message = ref("Hello Vue!");
    return {
      message,
      doc,
      reactiveArray,
    };
  },
  template: "#app-template",
  methods: {
    test() {
      const yarray = this.doc.getArray("my-array");
      yarray.push([1])
    }
  }
};

createApp(App).mount("#app");
