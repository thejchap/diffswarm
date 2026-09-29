// @ts-check

import { html } from "htm/preact";
import { memo } from "preact/compat";
import { useEffect, useRef, useState } from "preact/hooks";

// Metadata edits must not reconcile Pierre's imperatively managed DOM.
export const PierreViewer = memo(
  /** @param {{ raw: string, diffId: string, normalViewUrl: string }} props */
  function PierreViewer({ raw, diffId, normalViewUrl }) {
    const root = useRef(/** @type {HTMLDivElement | null} */ (null));
    const viewer = useRef(
      /** @type {import("@pierre/diffs").CodeView | undefined} */ (undefined),
    );
    const options = useRef(
      /** @type {import("@pierre/diffs").CodeViewOptions<undefined, undefined>} */ ({}),
    );
    const [status, setStatus] = useState("loading");

    useEffect(() => {
      let disposed = false;
      /** @type {(() => void) | undefined} */
      let terminateWorkers;
      const cleanUp = () => {
        disposed = true;
        viewer.current?.cleanUp();
        viewer.current = undefined;
        terminateWorkers?.();
        terminateWorkers = undefined;
      };
      const onPageHide = (/** @type {PageTransitionEvent} */ event) => {
        if (!event.persisted) cleanUp();
      };

      async function mount() {
        try {
          const [{ CodeView, parsePatchFiles }, workers] = await Promise.all([
            import("@pierre/diffs"),
            import("@pierre/diffs/worker"),
          ]);
          if (disposed || !root.current) return;
          terminateWorkers = workers.terminateWorkerPoolSingleton;
          const patches = parsePatchFiles(raw, diffId, true);
          /** @type {import("@pierre/diffs").CodeViewItem<undefined>[]} */
          const items = patches.flatMap((patch, patchIndex) =>
            patch.files.map((fileDiff, fileIndex) => ({
              id: `${diffId}:${patchIndex}:${fileIndex}`,
              type: "diff",
              fileDiff,
            })),
          );
          if (items.length === 0)
            throw new Error("No files found in this patch");
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
          options.current = {
            theme,
            diffStyle: "unified",
            overflow: "scroll",
            hunkSeparators: "metadata",
            disableFileHeader: items.length === 1,
            stickyHeaders: true,
          };
          viewer.current = new CodeView(options.current, workerPool);
          viewer.current.setup(root.current);
          viewer.current.setItems(items);
          await workerPool.initialize();
          if (!disposed) setStatus("ready");
        } catch (error) {
          if (disposed) return;
          cleanUp();
          setStatus("error");
          console.error("Pierre viewer failed:", error);
        }
      }

      void mount();
      window.addEventListener("pagehide", onPageHide);
      return () => {
        window.removeEventListener("pagehide", onPageHide);
        cleanUp();
      };
    }, [raw, diffId]);

    return html`
      <section aria-label="Pierre diff viewer">
        <div
          class="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-gray-200 dark:border-monokai-border text-xs text-gray-600 dark:text-monokai-muted"
        >
          <span>Pierre (experimental)</span>
          <div class="flex flex-wrap items-center gap-3">
            <label for="pierre-layout">Layout</label>
            <select
              id="pierre-layout"
              class="rounded border border-gray-200 dark:border-monokai-border bg-white dark:bg-monokai-bg px-2 py-1"
              disabled=${status !== "ready"}
              onChange=${(/** @type {Event} */ event) => {
                if (!(event.currentTarget instanceof HTMLSelectElement)) return;
                viewer.current?.setOptions({
                  ...options.current,
                  diffStyle:
                    event.currentTarget.value === "split" ? "split" : "unified",
                });
              }}
            >
              <option value="unified">Unified</option>
              <option value="split">Split</option>
            </select>
            <a class="underline" href=${normalViewUrl}>Open normal viewer</a>
          </div>
        </div>
        ${status !== "ready" &&
        html`
          <p
            class="p-4 text-sm"
            role=${status === "error" ? "alert" : "status"}
          >
            ${status === "error"
              ? "This diff could not be loaded in the experimental viewer. Use Open normal viewer to continue."
              : "Loading diff…"}
          </p>
        `}
        <div
          id="pierre-viewer"
          ref=${root}
          aria-label="Diff viewer"
          tabindex="0"
          style="height: 65dvh; min-height: 24rem; overflow: auto; --diffs-font-family: 'JetBrains Mono', monospace;"
        ></div>
      </section>
    `;
  },
);
