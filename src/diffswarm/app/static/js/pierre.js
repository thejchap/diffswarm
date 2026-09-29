// @ts-check

async function mount() {
  const root = document.getElementById("pierre-viewer");
  const status = document.getElementById("pierre-status");
  const layout = document.getElementById("pierre-layout");
  if (!root || !status || !(layout instanceof HTMLSelectElement)) return;

  /** @type {import("@pierre/diffs").CodeView | undefined} */
  let viewer;
  /** @type {(() => void) | undefined} */
  let terminateWorkers;
  const cleanUp = () => {
    viewer?.cleanUp();
    terminateWorkers?.();
  };

  try {
    const [{ CodeView, parsePatchFiles }, workers] = await Promise.all([
      import("@pierre/diffs"),
      import("@pierre/diffs/worker"),
    ]);
    terminateWorkers = workers.terminateWorkerPoolSingleton;
    const patches = parsePatchFiles(
      root.dataset.patch || "",
      root.dataset.diffId,
      true,
    );
    /** @type {import("@pierre/diffs").CodeViewItem<undefined>[]} */
    const items = patches.flatMap((patch, patchIndex) =>
      patch.files.map((fileDiff, fileIndex) => ({
        id: `${root.dataset.diffId}:${patchIndex}:${fileIndex}`,
        type: "diff",
        fileDiff,
      })),
    );
    if (items.length === 0) throw new Error("No files found in this patch");
    const theme = { dark: "pierre-dark", light: "pierre-light" };
    const workerPool = workers.getOrCreateWorkerPoolSingleton({
      poolOptions: {
        poolSize: 2,
        workerFactory: () =>
          new Worker(new URL("./pierre-worker.js", import.meta.url), {
            type: "module",
          }),
      },
      highlighterOptions: { theme },
    });
    /** @type {import("@pierre/diffs").CodeViewOptions<undefined, undefined>} */
    const options = {
      theme,
      diffStyle: "unified",
      overflow: "scroll",
      hunkSeparators: "metadata",
      stickyHeaders: true,
    };
    viewer = new CodeView(options, workerPool);
    viewer.setup(root);
    viewer.setItems(items);
    await workerPool.initialize();
    layout.disabled = false;
    layout.addEventListener("change", () => {
      viewer?.setOptions({
        ...options,
        diffStyle: layout.value === "split" ? "split" : "unified",
      });
    });
    status.hidden = true;
    // Release the serialized copy after parsing; the parsed items own the content.
    delete root.dataset.patch;
    window.addEventListener("pagehide", (event) => {
      if (!event.persisted) cleanUp();
    });
  } catch (error) {
    cleanUp();
    layout.disabled = true;
    status.hidden = false;
    status.textContent =
      "This diff could not be loaded in the experimental viewer. Use Open normal viewer to continue.";
    status.setAttribute("role", "alert");
    console.error("Pierre viewer failed:", error);
  }
}

void mount();
