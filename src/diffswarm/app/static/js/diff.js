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
    const yarray = doc.getArray("my-array");
    yarray.observe((event) => {
      console.log("yarray was modified");
    });
    wsProvider.on("status", (event) => {
      console.log(event.status); // logs "connected" or "disconnected"
      yarray.insert(0, ["val", "123", "456"]); // => "yarray was modified"
    });
    // every time a local or remote client modifies yarray, the observer is called
    const message = ref("Hello Vue!");
    return {
      message,
    };
  },
  template: "#app-template",
};

createApp(App).mount("#app");
