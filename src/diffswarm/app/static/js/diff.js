// @ts-check

import { html } from "htm/preact";
import { createContext, render } from "preact";
import { signal } from "@preact/signals";
import { useContext } from "preact/hooks";

const $APP = document.getElementById("app");
if (!$APP) {
  throw new Error("unable to find #app");
}
const { diffPrefetch: DIFF_PREFETCH } = $APP.dataset;

/**
 * @typedef {{
 *  diff: import("@preact/signals").Signal<any>,
 *  comments: import("@preact/signals").Signal<any[]>
 * }} AppStateType
 */

/**
 * @returns {AppStateType}
 */
function createAppState() {
  if (!DIFF_PREFETCH) {
    throw new Error("unable to load diff prefetch");
  }
  const diff = signal(/** @type {any} */ (JSON.parse(DIFF_PREFETCH)));
  const comments = signal([]);
  return { diff, comments };
}

const AppState = createContext(/** @type {AppStateType | null} */ (null));

function useDiff() {
  const ctx = useContext(AppState);
  if (!ctx) {
    throw new Error("useItems must be used within <ItemsProvider>");
  }
  return ctx;
}

/**
 * components
 */
function HunkRename() {
  const hunkId = "test";
  const handleEdit = () => {};
  return html`
    <div class="flex items-center gap-2 group">
      <span
        class="text-sm font-code font-semibold text-gray-900 dark:text-monokai-text tracking-tight"
      >
        ${hunkId}
      </span>
      <button
        onClick=${handleEdit}
        class="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-gray-100 dark:hover:bg-monokai-elevated transition-all duration-200 hover:scale-105"
        aria-label="Rename hunk"
        title="Rename hunk"
      >
        <Edit3
          class="w-3 h-3 text-gray-400 dark:text-monokai-muted hover:text-gray-600 dark:hover:text-monokai-text"
        />
      </button>
    </div>
  `;
}

function HunkHeader() {
  const additions = 5;
  const deletions = 3;
  const commentCount = 1;
  const isCollapsed = false;
  const isCompleted = false;
  const hunkIndex = 0;
  const isCopied = false;
  const onToggleComplete = () => {};
  const onAddComment = () => {};
  const onCopy = () => {};
  const onShare = () => {};
  const onToggleCollapse = () => {};
  const onRenameHunk = () => {};
  return html`
    <div
      class="px-4 py-3 bg-gradient-to-r from-gray-50/80 to-gray-50/40 dark:from-gray-800/60 dark:to-gray-800/30 border-b border-gray-200/50 dark:border-gray-700/50"
    >
      <div class="flex items-start gap-3">
        <button
          onClick=${onToggleComplete}
          class="mt-0.5 flex-shrink-0 transition-all duration-200 hover:scale-110 transform"
          aria-label=${`Mark hunk ${hunkIndex + 1} as ${isCompleted ? "incomplete" : "complete"}`}
        >
          ${isCompleted
            ? html`
                <div
                  class="w-5 h-5 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shadow-sm"
                >
                  <i
                    data-lucide="check"
                    class="w-3 h-3 text-white font-bold"
                  ></i>
                </div>
              `
            : html`
                <img
                  src="https://unpkg.com/lucide-static@latest/icons/circle.svg"
                  class="w-5 h-5 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                />
              `}
        </button>

        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between">
            <div class="flex-1">
              <div class=${isCompleted ? "line-through opacity-60" : ""}>
                <${HunkRename} hunkId=${"test"} onRename=${onRenameHunk} />
              </div>
              <div class="flex items-center gap-3 mt-1">
                <span
                  class="font-code text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded"
                >
                  @@ -1 +1,2 @@
                  <!-- <SearchHighlight text={hunk.header} searchQuery={searchQuery} /> -->
                </span>
                <div class="flex items-center gap-2 text-xs">
                  <span
                    class="text-emerald-600 dark:text-emerald-400 font-semibold bg-emerald-50 dark:bg-emerald-900/20 px-1.5 py-0.5 rounded"
                  >
                    +${additions}
                  </span>
                  <span
                    class="text-red-600 dark:text-red-400 font-semibold bg-red-50 dark:bg-red-900/20 px-1.5 py-0.5 rounded"
                  >
                    -${deletions}
                  </span>
                  ${commentCount > 0 &&
                  html`
                    <div
                      class="flex items-center gap-1 bg-blue-50 dark:bg-blue-900/20 px-2 py-1 rounded-full border border-blue-200 dark:border-blue-700 shadow-sm"
                    >
                      <MessageSquare class="w-3.5 h-3.5 text-blue-500" />
                      <span
                        class="text-blue-600 dark:text-blue-400 text-xs font-semibold"
                        >${commentCount}</span
                      >
                    </div>
                  `}
                </div>
              </div>
            </div>

            <div class="flex items-center gap-1 ml-3">
              <button
                onClick=${onAddComment}
                class="p-2 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-all duration-200 group hover:scale-105 shadow-sm"
                aria-label="Add comment to hunk"
                title="Add comment to hunk"
              >
                <MessageSquare
                  class="w-3.5 h-3.5 text-gray-400 group-hover:text-blue-500 transition-colors"
                />
              </button>
              <button
                onClick=${onCopy}
                class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-all duration-200 group hover:scale-105 shadow-sm"
                aria-label="Copy hunk"
                title="Copy hunk"
              >
                <Copy
                  class=${`w-3.5 h-3.5 transition-colors ${isCopied ? "text-emerald-500" : "text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300"}`}
                />
              </button>
              <button
                onClick=${onShare}
                class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-all duration-200 group hover:scale-105 shadow-sm"
                aria-label="Share hunk"
                title="Share hunk"
              >
                <Share2
                  class="w-3.5 h-3.5 text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300 transition-colors"
                />
              </button>
              <button
                onClick=${onToggleCollapse}
                class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-all duration-200 hover:scale-105 shadow-sm"
                aria-label=${`${isCollapsed ? "Expand" : "Collapse"} hunk details`}
              >
                ${isCollapsed
                  ? html`
                      <ChevronRight
                        class="w-3.5 h-3.5 text-gray-400 transition-transform"
                      />
                    `
                  : html`
                      <ChevronDown
                        class="w-3.5 h-3.5 text-gray-400 transition-transform"
                      />
                    `}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

/** @param {any} props */
function Line({ line }) {
  /** @param {Number} number */
  const renderLineNumber = (number) => {
    return number
      ? html`<span
          class="text-gray-500 dark:text-gray-400 select-none font-medium"
          >${number}</span
        >`
      : html`<span class="text-gray-300 dark:text-gray-600 select-none"
          >·</span
        >`;
  };
  /**
   * @param {any} type
   */
  const getLineStyles = (type) => {
    switch (type) {
      case "ADD":
        return "diff-add border-l-2 transition-diff cursor-pointer";
      case "DELETE":
        return "diff-remove border-l-2 transition-diff cursor-pointer";
      case "CONTEXT":
        return "diff-context transition-diff cursor-pointer";
      default:
        return "transition-diff cursor-pointer hover:bg-gray-50/80 dark:hover:bg-gray-800/50";
    }
  };
  function handleLineClick() {}
  /**
   * @param {any} _
   */
  function getLineIcon(_) {}
  const totalComments = 0;
  console.log(line);
  return html`
    <div>
      <div
        class=${`flex ${getLineStyles(line.type)} group relative`}
        onClick=${handleLineClick}
      >
        <div
          class="w-10 px-2 py-1 text-right text-xs select-none font-code border-r border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/50"
        >
          ${renderLineNumber(line.line_number_old)}
        </div>
        <div
          class="w-10 px-2 py-1 text-right text-xs select-none font-code border-r border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/50"
        >
          ${renderLineNumber(line.line_number_new)}
        </div>
        <div
          class="w-6 px-1 py-1 flex items-center justify-center flex-shrink-0 bg-gray-50/30 dark:bg-gray-800/30"
        >
          ${getLineIcon(line.type)}
        </div>
        <div
          class="flex-1 px-3 py-1 font-code text-xs leading-relaxed whitespace-pre-wrap break-all"
        >
          ${line.content}
          <!-- <SearchHighlight text={line.content || " "} searchQuery={searchQuery} /> -->
        </div>

        <div class="w-14 px-2 py-1 flex items-center justify-center gap-1">
          ${totalComments > 0 &&
          html` <div
            class="w-4 h-4 rounded-full bg-blue-500 dark:bg-blue-600 flex items-center justify-center shadow-sm"
          >
            <span class="text-xs text-white font-semibold">
              ${totalComments}
            </span>
          </div>`}
          <div
            class="opacity-0 group-hover:opacity-100 p-0.5 rounded-md bg-blue-100 dark:bg-blue-900/40 transition-all duration-200"
          >
            <!-- <MessageSquare class="w-3 h-3 text-blue-500 dark:text-blue-400" /> -->
          </div>
        </div>
        <div
          class="absolute inset-0 opacity-0 group-hover:opacity-5 bg-blue-500 transition-opacity duration-200 pointer-events-none"
        />
      </div>
    </div>
  `;
}

/**
 * @param {any} props
 */
function Hunk({ hunk }) {
  return html`
    <div class="dark:bg-monokai-bg transition-all duration-300">
      <!-- hunk header -->
      <${HunkHeader} />

      <!-- hunk body -->
      <div
        class="font-code text-sm border-t border-gray-200/50 dark:border-monokai-border/50"
      >
        <!-- lines -->

        ${hunk.lines.map(
          /** @param {any} line */
          (line) => html`<${Line} line=${line} />`,
        )}
        <!-- test -->
        <!-- diffline -->
      </div>
    </div>
  `;
}

function FileHeader() {
  const { diff, comments } = useDiff();
  console.log(diff.value);
  function onClick() {
    comments.value = [...comments.value, 1];
  }
  return html`
    <div
      class="px-4 py-4 border-b border-gray-200 dark:border-monokai-border bg-gradient-to-r from-white to-gray-50/50 dark:from-monokai-bg dark:to-monokai-surface/50"
      onClick=${onClick}
    >
      <div class="flex items-center justify-between mb-4">
        <div class="flex-1">
          <div class="flex items-center gap-4 mb-3">
            <!-- filerename -->

            <div class="flex items-center gap-2 group">
              <h1
                class="text-lg font-code font-semibold text-gray-900 dark:text-monokai-text tracking-tight"
              >
                my name
              </h1>
            </div>
          </div>
          <div class="space-y-1 mb-3 text-xs font-code">
            ${diff.value.from_filename &&
            html`
              <div class="flex items-center gap-2">
                <span
                  class="text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 px-2 py-1 rounded font-medium"
                >
                  −
                </span>
                <span class="text-gray-600 dark:text-monokai-muted"
                  >${diff.value.from_filename}</span
                >
              </div>
            `}
            ${diff.value.to_filename &&
            html`
              <div class="flex items-center gap-2">
                <span
                  class="text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20 px-2 py-1 rounded font-medium"
                >
                  +
                </span>
                <span class="text-gray-600 dark:text-monokai-muted"
                  >${diff.value.to_filename}</span
                >
              </div>
            `}
          </div>
        </div>
      </div>

      <!-- search wrapper -->
      <div class="flex items-center gap-4">
        <div class="flex-1">
          <div class="relative flex-1 w-full">
            <div
              class="relative flex items-center transition-all duration-200 border border-gray-200 dark:border-monokai-border rounded-lg bg-gray-50 dark:bg-monokai-elevated hover:bg-gray-100 dark:hover:bg-monokai-surface"
            >
              <input
                type="text"
                placeholder="Search hunks and content... (⌘K)"
                class="flex-1 px-3 py-2 text-sm bg-transparent text-gray-900 dark:text-monokai-text placeholder-gray-500 dark:placeholder-monokai-muted focus:outline-none"
              />
            </div>
          </div>
        </div>
        <!-- <HunkFilter /> -->
      </div>

      <!-- next -->
    </div>
  `;
}

function App() {
  const { diff } = useDiff();
  return html`
    <!-- outermost - DiffViewerDemo -->
    <div
      class="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-100 dark:from-monokai-bg dark:via-monokai-bg dark:to-monokai-surface py-8"
    >
      <!-- DiffViewer  -->
      <div class="max-w-6xl mx-auto">
        <!--  main content, original header  -->
        <div
          class="bg-white dark:bg-monokai-bg border border-gray-200 dark:border-monokai-border rounded-2xl shadow-elegant overflow-hidden"
        >
          <!--  header - stays in original position  -->
          <div class="border-b border-gray-200 dark:border-monokai-border">
            <!-- fileheader -->
            <${FileHeader} />
          </div>

          <!-- main content -->
          <div>
            <div
              class="divide-y divide-gray-200/50 dark:divide-monokai-border/50"
            >
              ${diff.value.hunks.map(
                /** @param {any} hunk */
                (hunk) => html` <${Hunk} hunk=${hunk} /> `,
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * set up and mount the app
 */
render(
  html`
    <${AppState.Provider} value=${createAppState()}>
      <${App} />
    <//>
  `,
  $APP,
);
