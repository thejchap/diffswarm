import { createApp } from "vue";
import * as Y from "yjs";
import { ref } from "vue";

const Test = {
  template: "#my-template-element",
};

const App = {
  components: {
    Test,
  },
  setup() {
    const doc = new Y.Doc();
    const yarray = doc.getArray("my-array");
    yarray.observe((event) => {
      console.log("yarray was modified");
    });
    // every time a local or remote client modifies yarray, the observer is called
    yarray.insert(0, ["val"]); // => "yarray was modified"
    const message = ref("Hello Vue!");
    return {
      message,
    };
  },
  template: "#app-template",
};

createApp(App).mount("#app");
