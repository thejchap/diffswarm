// @ts-check

import { html } from "htm/preact";
import { createContext, render } from "preact";
import { signal } from "@preact/signals";
import { useContext, useState, useEffect, useRef } from "preact/hooks";

const $APP = document.getElementById("app");
if (!$APP) {
  throw new Error("unable to find #app");
}
const { diffPrefetch: DIFF_PREFETCH, commentsPrefetch: COMMENTS_PREFETCH } =
  $APP.dataset;

/**
 * Updates URL search parameter without page reload
 * @param {string} key
 * @param {string} value
 */
function updateURLParameter(key, value) {
  const url = new URL(window.location.href);
  if (value && value.trim()) {
    url.searchParams.set(key, value);
  } else {
    url.searchParams.delete(key);
  }
  window.history.replaceState({}, "", url);
}

/**
 * @typedef {{
 *  id: string,
 *  type: "ADD" | "DELETE" | "CONTEXT",
 *  content: string,
 *  line_number_old: number | null,
 *  line_number_new: number | null
 * }} Line
 */

/**
 * @typedef {{
 *  id: string | null,
 *  name: string | null,
 *  from_start: number,
 *  from_count: number,
 *  to_start: number,
 *  to_count: number,
 *  completed_at: string | null,
 *  lines: Line[]
 * }} Hunk
 */

/**
 * @typedef {{
 *  id: string,
 *  name: string,
 *  raw: string,
 *  from_filename: string,
 *  from_timestamp: Date | null,
 *  to_filename: string,
 *  to_timestamp: Date | null,
 *  hunks: Hunk[]
 * }} Diff
 */

/**
 * @typedef {{
 *  id: string,
 *  text: string,
 *  author: string,
 *  timestamp: Date,
 *  hunkId: string,
 *  diffId?: string,
 *  lineIndex?: number,
 *  startOffset?: number,
 *  endOffset?: number,
 *  parentId?: string,
 *  selectedText?: string
 * }} Comment
 */

/**
 * @typedef {{
 *  hunkId: string,
 *  lineIndex?: number,
 *  selectedText?: string,
 *  startOffset?: number,
 *  endOffset?: number,
 *  parentId?: string
 * }} CommentFormState
 */

/**
 * @typedef {"all" | "completed" | "uncompleted"} FilterType
 */

/**
 * @typedef {{
 *  diff: import("@preact/signals").Signal<Diff>,
 *  comments: import("@preact/signals").Signal<Comment[]>,
 *  isEditing: import("@preact/signals").Signal<boolean>,
 *  editValue: import("@preact/signals").Signal<string>,
 *  collapsedHunks: import("@preact/signals").Signal<Set<number>>,
 *  currentFilter: import("@preact/signals").Signal<FilterType>,
 *  searchQuery: import("@preact/signals").Signal<string>
 * }} AppStateType
 */

/**
 * @returns {AppStateType}
 */
function createAppState() {
  if (!DIFF_PREFETCH) {
    throw new Error("unable to load diff prefetch");
  }
  if (!COMMENTS_PREFETCH) {
    throw new Error("unable to load comments prefetch");
  }

  const diff = signal(/** @type {Diff} */ (JSON.parse(DIFF_PREFETCH)));

  // Parse and transform prefetched comments to frontend format
  const prefetchedComments = JSON.parse(COMMENTS_PREFETCH);
  const transformedComments = prefetchedComments.map(
    (/** @type {any} */ comment) => {
      // Find the hunk index by ULID to create frontend hunk-{index} format
      const hunkIndex = diff.value.hunks.findIndex(
        (h) => h.id === comment.hunk_id,
      );
      return {
        ...comment,
        hunkId: hunkIndex >= 0 ? `hunk-${hunkIndex}` : comment.hunk_id, // Convert to hunk-{index} for frontend
        timestamp: new Date(comment.timestamp),
        diffId: comment.diff_id,
        lineIndex: comment.line_index === -1 ? undefined : comment.line_index,
        startOffset: comment.start_offset,
        endOffset: comment.end_offset,
        parentId: comment.in_reply_to,
      };
    },
  );

  const comments = signal(/** @type {Comment[]} */ (transformedComments));

  // File rename state
  const isEditing = signal(false);
  const editValue = signal("");

  // Collapsed hunks state
  const collapsedHunks = signal(/** @type {Set<number>} */ (new Set()));

  // Filter state
  const currentFilter = signal(/** @type {FilterType} */ ("all"));

  // Search state - initialize from URL parameter
  const urlParams = new URLSearchParams(window.location.search);
  const initialSearchQuery = urlParams.get("search") || "";
  const searchQuery = signal(initialSearchQuery);

  return {
    diff,
    comments,
    isEditing,
    editValue,
    collapsedHunks,
    currentFilter,
    searchQuery,
  };
}

/**
 * Converts a hunk to its textual unified diff representation
 * @param {Hunk} hunk - The hunk to convert
 * @returns {string} - The hunk as text
 */
function hunkToText(hunk) {
  const header = `@@ -${hunk.from_start},${hunk.from_count} +${hunk.to_start},${hunk.to_count} @@`;
  const lines = hunk.lines
    .map((line) => {
      const prefix =
        line.type === "ADD" ? "+" : line.type === "DELETE" ? "-" : " ";
      return prefix + line.content;
    })
    .join("\n");
  return header + "\n" + lines;
}

// Icon components using Lucide icons
/** @param {{ class: string }} props */
function MessageSquare({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>`;
}

/** @param {{ class: string }} props */
function Edit3({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
  </svg>`;
}

/** @param {{ class: string }} props */
function Copy({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
    <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
  </svg>`;
}

/** @param {{ class: string }} props */
function Search({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.35-4.35" />
  </svg>`;
}

/** @param {{ class: string }} props */
function X({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </svg>`;
}

/** @param {{ class: string }} props */
function Link({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
  </svg>`;
}

/** @param {{ class: string }} props */
function Share2({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <circle cx="18" cy="5" r="3" />
    <circle cx="6" cy="12" r="3" />
    <circle cx="18" cy="19" r="3" />
    <path d="m8.59 13.51 6.83 3.98" />
    <path d="m15.41 6.51-6.82 3.98" />
  </svg>`;
}

/** @param {{ class: string }} props */
function ChevronDown({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="m6 9 6 6 6-6" />
  </svg>`;
}

/** @param {{ class: string }} props */
function ChevronRight({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="m9 18 6-6-6-6" />
  </svg>`;
}

/** @param {{ class: string }} props */
function Plus({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="M5 12h14" />
    <path d="M12 5v14" />
  </svg>`;
}

/** @param {{ class: string }} props */
function MoreVertical({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <circle cx="12" cy="12" r="1" />
    <circle cx="12" cy="5" r="1" />
    <circle cx="12" cy="19" r="1" />
  </svg>`;
}

/** @param {{ class: string }} props */
function Reply({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <polyline points="9,17 4,12 9,7" />
    <path d="M20 18v-2a4 4 0 0 0-4-4H4" />
  </svg>`;
}

/** @param {{ class: string }} props */
function Trash2({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="m3 6 18 0" />
    <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
    <path d="M8 6V4c0-1 1-2 2-2h4c0 1 1 2 2 2v2" />
  </svg>`;
}

/** @param {{ class: string }} props */
function List({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <line x1="8" y1="6" x2="21" y2="6" />
    <line x1="8" y1="12" x2="21" y2="12" />
    <line x1="8" y1="18" x2="21" y2="18" />
    <line x1="3" y1="6" x2="3.01" y2="6" />
    <line x1="3" y1="12" x2="3.01" y2="12" />
    <line x1="3" y1="18" x2="3.01" y2="18" />
  </svg>`;
}

/** @param {{ class: string }} props */
function Check({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="M20 6 9 17l-5-5" />
  </svg>`;
}

/** @param {{ class: string }} props */
function Circle({ class: className }) {
  return html`<svg
    class="${className}"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <circle cx="12" cy="12" r="10" />
  </svg>`;
}

/**
 * SearchBar component for search input with keyboard shortcuts
 * @param {{ searchQuery: string, onSearchChange: (query: string) => void, resultCount: number, totalHunks: number, isSearching: boolean }} props
 */
function SearchBar({
  searchQuery,
  onSearchChange,
  resultCount,
  totalHunks,
  isSearching,
}) {
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef(/** @type {HTMLInputElement | null} */ (null));

  // Keyboard shortcut to focus search (Cmd/Ctrl + K)
  useEffect(() => {
    const handleKeyDown = (/** @type {KeyboardEvent} */ e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === "Escape" && isFocused) {
        inputRef.current?.blur();
        if (searchQuery) {
          onSearchChange("");
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isFocused, searchQuery, onSearchChange]);

  const clearSearch = () => {
    onSearchChange("");
    inputRef.current?.focus();
  };

  return html`
    <div class="relative flex-1 w-full">
      <div
        class=${`relative flex items-center transition-all duration-200 ${
          isFocused
            ? "ring-2 ring-blue-500 dark:ring-blue-400 bg-white dark:bg-monokai-surface"
            : "bg-gray-50 dark:bg-monokai-elevated hover:bg-gray-100 dark:hover:bg-monokai-surface"
        } border border-gray-200 dark:border-monokai-border rounded-lg`}
      >
        <${Search}
          class="w-4 h-4 text-gray-400 dark:text-monokai-muted ml-3 flex-shrink-0"
        />
        <input
          ref=${inputRef}
          type="text"
          value=${searchQuery}
          onInput=${(/** @type {Event} */ e) =>
            onSearchChange(/** @type {HTMLInputElement} */ (e.target).value)}
          onFocus=${() => setIsFocused(true)}
          onBlur=${() => setIsFocused(false)}
          placeholder="Search hunks and content... (⌘K)"
          class="flex-1 px-3 py-2 text-sm bg-transparent text-gray-900 dark:text-monokai-text placeholder-gray-500 dark:placeholder-monokai-muted focus:outline-none"
        />
        ${searchQuery &&
        html`
          <div class="flex items-center gap-2 px-2">
            <span
              class="text-xs text-gray-500 dark:text-monokai-muted whitespace-nowrap"
            >
              ${isSearching
                ? "Searching..."
                : resultCount > 0
                  ? `${resultCount} of ${totalHunks} hunks match`
                  : "No matches found"}
            </span>
            <button
              onClick=${clearSearch}
              class="p-1 rounded-md hover:bg-gray-200 dark:hover:bg-monokai-border transition-colors cursor-pointer"
              aria-label="Clear search"
            >
              <${X} class="w-3.5 h-3.5 text-gray-400 dark:text-monokai-muted" />
            </button>
          </div>
        `}
      </div>
    </div>
  `;
}

/**
 * SearchHighlight component for highlighting search matches in text
 * @param {{ text: string, searchQuery: string, className?: string }} props
 */
function SearchHighlight({ text, searchQuery, className = "" }) {
  if (!searchQuery.trim()) {
    return html`<span class="${className}">${text}</span>`;
  }

  const regex = new RegExp(
    `(${searchQuery.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`,
    "gi",
  );
  const parts = text.split(regex);

  return html`
    <span class="${className}">
      ${parts.map((part, index) =>
        regex.test(part)
          ? html`
              <mark
                key=${index}
                class="bg-yellow-200 dark:bg-yellow-900/50 text-yellow-900 dark:text-yellow-200 px-0.5 rounded-sm font-medium"
              >
                ${part}
              </mark>
            `
          : part,
      )}
    </span>
  `;
}

/**
 * CopyButton component for copying text to clipboard with visual feedback
 * @param {{ text: string, ariaLabel?: string, title?: string, className?: string }} props
 */
function CopyButton({
  text,
  ariaLabel = "Copy to clipboard",
  title,
  className = "",
}) {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = async (/** @type {Event} */ e) => {
    e.stopPropagation(); // Prevent event bubbling
    try {
      await navigator.clipboard.writeText(text);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  return html`
    <button
      onClick=${handleCopy}
      class="${className ||
      "p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-monokai-elevated transition-all duration-200 group hover:scale-105 shadow-sm border border-transparent hover:border-gray-200 dark:hover:border-gray-600"} cursor-pointer"
      aria-label=${ariaLabel}
      title=${title || ariaLabel}
    >
      ${isCopied
        ? html`<${Check}
            class="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 transition-colors"
          />`
        : html`<${Copy}
            class="w-3.5 h-3.5 text-gray-400 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors"
          />`}
    </button>
  `;
}

/**
 * CopyLinkButton component for copying line link to clipboard with visual feedback
 * @param {{ lineId: string, ariaLabel?: string, title?: string, className?: string }} props
 */
function CopyLinkButton({
  lineId,
  ariaLabel = "Copy link to line",
  title,
  className = "",
}) {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopyLink = async (/** @type {Event} */ e) => {
    e.stopPropagation(); // Prevent event bubbling
    try {
      const link = `${window.location.origin}${window.location.pathname}?search=${encodeURIComponent(lineId || "")}`;
      await navigator.clipboard.writeText(link);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy link:", err);
    }
  };

  return html`
    <button
      onClick=${handleCopyLink}
      class="${className ||
      "p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-monokai-elevated transition-all duration-200 group hover:scale-105 shadow-sm border border-transparent hover:border-gray-200 dark:hover:border-gray-600"} cursor-pointer"
      aria-label=${ariaLabel}
      title=${title || ariaLabel}
    >
      ${isCopied
        ? html`<${Check}
            class="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 transition-colors"
          />`
        : html`<${Link}
            class="w-3.5 h-3.5 text-gray-400 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors"
          />`}
    </button>
  `;
}

/**
 * Hunk filter component with dropdown
 * @param {{ currentFilter: FilterType, onFilterChange: (filter: FilterType) => void, completedCount: number, uncompletedCount: number, totalCount: number }} props
 */
function HunkFilter({
  currentFilter,
  onFilterChange,
  completedCount,
  uncompletedCount,
  totalCount,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const buttonRef = useRef(/** @type {HTMLButtonElement | null} */ (null));
  const [dropdownStyle, setDropdownStyle] = useState({});

  const filterOptions = [
    {
      value: /** @type {FilterType} */ ("all"),
      label: "All hunks",
      icon: List,
      count: totalCount,
      color: "text-gray-600 dark:text-gray-400",
      bgColor: "bg-gray-100 dark:bg-gray-700",
    },
    {
      value: /** @type {FilterType} */ ("completed"),
      label: "Completed",
      icon: Check,
      count: completedCount,
      color: "text-emerald-600 dark:text-emerald-400",
      bgColor: "bg-emerald-100 dark:bg-emerald-900/20",
    },
    {
      value: /** @type {FilterType} */ ("uncompleted"),
      label: "Uncompleted",
      icon: Circle,
      count: uncompletedCount,
      color: "text-blue-600 dark:text-blue-400",
      bgColor: "bg-blue-100 dark:bg-blue-900/20",
    },
  ];

  const currentOption = filterOptions.find(
    (option) => option.value === currentFilter,
  );

  // Calculate dropdown position when opening
  const handleToggle = () => {
    if (!isOpen && buttonRef.current) {
      const buttonRect = buttonRef.current.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const dropdownHeight = 200; // Approximate dropdown height
      const spaceBelow = viewportHeight - buttonRect.bottom;

      let top = buttonRect.bottom + 4; // 4px margin
      if (spaceBelow < dropdownHeight && buttonRect.top > dropdownHeight) {
        top = buttonRect.top - dropdownHeight - 4;
      }

      setDropdownStyle({
        position: "fixed",
        top: `${top}px`,
        left: `${buttonRect.left}px`,
        width: "192px", // w-48 = 12rem = 192px
        zIndex: 9999,
      });
    }
    setIsOpen(!isOpen);
  };

  return html`
    <div class="relative">
      <button
        ref=${buttonRef}
        onClick=${handleToggle}
        class="flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors cursor-pointer"
        aria-label="Filter hunks"
      >
        ${currentOption &&
        html`
          <${currentOption.icon} class="w-3.5 h-3.5" />
          <span>${currentOption.label}</span>
          <span
            class="${currentOption.bgColor} ${currentOption.color} px-1.5 py-0.5 rounded-full text-xs font-semibold"
          >
            ${currentOption.count}
          </span>
        `}
        <svg
          class="${`w-3 h-3 transition-transform ${isOpen ? "rotate-180" : ""}`}"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      ${isOpen &&
      html`
        <!-- Backdrop -->
        <div class="fixed inset-0 z-10" onClick=${() => setIsOpen(false)} />

        <!-- Dropdown -->
        <div
          style=${dropdownStyle}
          class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg shadow-elegant overflow-hidden"
        >
          ${filterOptions.map(
            (option) => html`
              <button
                key=${option.value}
                onClick=${() => {
                  onFilterChange(option.value);
                  setIsOpen(false);
                }}
                class="${`w-full flex items-center gap-3 px-4 py-3 text-left text-xs hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors cursor-pointer ${
                  currentFilter === option.value
                    ? "bg-blue-50 dark:bg-blue-900/20"
                    : ""
                }`}"
              >
                <${option.icon} class="${`w-3.5 h-3.5 ${option.color}`}" />
                <span
                  class="flex-1 font-medium text-gray-900 dark:text-gray-100"
                  >${option.label}</span
                >
                <span
                  class="${`${option.bgColor} ${option.color} px-1.5 py-0.5 rounded-full text-xs font-semibold`}"
                >
                  ${option.count}
                </span>
                ${currentFilter === option.value &&
                html`<div class="w-2 h-2 rounded-full bg-blue-500" />`}
              </button>
            `,
          )}
        </div>
      `}
    </div>
  `;
}

/**
 * Component for renaming hunks inline
 * @param {{ hunk: Hunk, onRename: (hunkId: string, newName: string) => Promise<void> }} props
 */
function HunkRename({ hunk, onRename }) {
  const appState = useContext(AppState);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const inputRef = useRef(/** @type {HTMLInputElement | null} */ (null));

  const validateName = (/** @type {string} */ name) => name.trim().length > 0;
  const isValid = () => validateName(editValue);

  const handleEdit = () => {
    setEditValue(hunk.name || hunk.id || "");
    setIsEditing(true);
  };

  // Auto-focus and select text when entering edit mode
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleSave = async () => {
    const trimmedValue = editValue.trim();
    if (!validateName(trimmedValue) || trimmedValue === hunk.name) {
      setIsEditing(false);
      return;
    }

    setIsLoading(true);
    try {
      await onRename(hunk.id || "", trimmedValue);
    } catch (error) {
      console.error("Failed to update hunk name:", error);
    }
    setIsLoading(false);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditValue(hunk.name || hunk.id || "");
    setIsEditing(false);
  };

  const handleKeyDown = (/** @type {KeyboardEvent} */ e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      handleCancel();
    }
  };

  const handleChange = (/** @type {Event} */ e) => {
    const target = /** @type {HTMLInputElement} */ (e.target);
    setEditValue(target.value);
  };

  const handleSubmit = (/** @type {Event} */ e) => {
    e.preventDefault();
    if (isValid()) handleSave();
  };

  if (isEditing) {
    return html`
      <form onSubmit=${handleSubmit} class="flex items-center gap-2">
        <div class="flex-1 relative">
          <input
            ref=${inputRef}
            type="text"
            value=${editValue}
            onChange=${handleChange}
            onKeyDown=${handleKeyDown}
            class="w-full px-2 py-1 text-sm font-code font-medium bg-white dark:bg-monokai-surface border rounded-md focus:outline-none focus:ring-2 transition-colors ${isValid()
              ? "border-gray-300 dark:border-monokai-border focus:ring-blue-500 text-gray-900 dark:text-monokai-text"
              : "border-red-300 dark:border-red-600 focus:ring-red-500 text-red-700 dark:text-red-400"}"
            placeholder="Enter hunk name..."
            disabled=${isLoading}
          />
          ${!isValid() &&
          html`
            <div
              class="absolute top-full left-0 mt-1 px-2 py-1 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded text-xs text-red-600 dark:text-red-400 whitespace-nowrap z-10"
            >
              Name cannot be empty
            </div>
          `}
        </div>
        <button
          type="submit"
          disabled=${!isValid() || editValue.trim() === hunk.name || isLoading}
          class="p-1 rounded-md hover:bg-emerald-100 dark:hover:bg-emerald-900/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Save hunk name"
          title="Save (Enter)"
        >
          <${Check} class="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
        </button>
        <button
          onClick=${handleCancel}
          disabled=${isLoading}
          class="p-1 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
          aria-label="Cancel rename"
          title="Cancel (Esc)"
          type="button"
        >
          <${X} class="w-3 h-3 text-gray-500 dark:text-gray-400" />
        </button>
      </form>
    `;
  }

  return html`
    <div class="flex items-center gap-1 group">
      <span
        onClick=${handleEdit}
        class="text-sm font-code font-medium text-gray-900 dark:text-monokai-text cursor-pointer hover:text-gray-900 dark:hover:text-monokai-text"
        title="Click to rename hunk"
      >
        <${SearchHighlight}
          text=${hunk.name || hunk.id}
          searchQuery=${appState?.searchQuery.value || ""}
        />
      </span>
      <button
        onClick=${handleEdit}
        class="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-gray-100 dark:hover:bg-monokai-elevated transition-all duration-200 hover:scale-105"
        aria-label="Rename hunk"
        title="Rename hunk"
      >
        <${Edit3}
          class="w-3 h-3 text-gray-400 dark:text-monokai-muted hover:text-gray-600 dark:hover:text-monokai-text"
        />
      </button>
    </div>
  `;
}

const AppState = createContext(/** @type {AppStateType | null} */ (null));

function useDiff() {
  const ctx = useContext(AppState);
  if (!ctx) {
    throw new Error("useDiff must be used within <AppState.Provider>");
  }
  return ctx.diff;
}

/**
 * comment helper functions
 */
function useComments() {
  const ctx = useContext(AppState);
  if (!ctx) {
    throw new Error("useComments must be used within AppState Provider");
  }

  const { comments, diff } = ctx;

  const addComment = async (
    /** @type {CommentFormState} */ formState,
    /** @type {string} */ text,
  ) => {
    try {
      // Convert hunk-{index} to actual hunk ULID
      const hunkIndex = parseInt(formState.hunkId.replace("hunk-", ""));
      const actualHunkId = diff.value.hunks[hunkIndex]?.id;

      if (!actualHunkId) {
        console.error("Could not find hunk ID for", formState.hunkId);
        return;
      }

      // Generate temporary ID for optimistic update
      const tempId = `temp_${Date.now()}_${Math.random()}`;

      // Create optimistic comment
      const optimisticComment = {
        id: tempId,
        text: text.trim(),
        author: "Current User",
        timestamp: new Date(),
        hunkId: formState.hunkId,
        diffId: diff.value.id,
        selectedText: formState.selectedText,
        lineIndex: formState.lineIndex,
        startOffset: formState.startOffset || 0,
        endOffset: formState.endOffset || text.length,
        parentId: formState.parentId || undefined,
      };

      // Add optimistic comment to local state immediately
      comments.value = [...comments.value, optimisticComment];

      const response = await fetch("/api/comments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text.trim(),
          author: "Current User",
          hunk_id: actualHunkId, // Use actual hunk ULID
          diff_id: diff.value.id,
          line_index: formState.lineIndex ?? -1, // Use -1 for hunk-level comments
          start_offset: formState.startOffset || 0,
          end_offset: formState.endOffset || text.length,
          in_reply_to: formState.parentId || null,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        // Replace optimistic comment with server response
        const newComment = {
          ...result.comment,
          hunkId: formState.hunkId, // Keep frontend hunk ID format
          diffId: diff.value.id,
          selectedText: formState.selectedText,
          timestamp: new Date(result.comment.timestamp), // Convert timestamp to Date object
          lineIndex:
            result.comment.line_index === -1
              ? undefined
              : result.comment.line_index,
          startOffset: result.comment.start_offset,
          endOffset: result.comment.end_offset,
          parentId: result.comment.in_reply_to,
        };

        // Replace optimistic comment with real one
        comments.value = comments.value.map((comment) =>
          comment.id === tempId ? newComment : comment,
        );
      } else {
        // Remove optimistic comment on failure
        comments.value = comments.value.filter(
          (comment) => comment.id !== tempId,
        );
        console.error("Failed to create comment:", await response.text());
      }
    } catch (error) {
      console.error("Error creating comment:", error);
    }
  };

  const deleteComment = async (/** @type {string} */ commentId) => {
    try {
      // Helper function to find all comments to delete (including nested replies)
      const findCommentsToDelete = (
        /** @type {Comment[]} */ allComments,
        /** @type {string} */ targetId,
      ) => {
        const idsToDelete = new Set([targetId]);
        let foundMore = true;

        while (foundMore) {
          foundMore = false;
          for (const comment of allComments) {
            if (
              comment.parentId &&
              idsToDelete.has(comment.parentId) &&
              !idsToDelete.has(comment.id)
            ) {
              idsToDelete.add(comment.id);
              foundMore = true;
            }
          }
        }

        return idsToDelete;
      };

      // Store original comments and deleted comments for rollback
      const originalComments = [...comments.value];
      const idsToDelete = findCommentsToDelete(originalComments, commentId);
      const deletedComments = originalComments.filter((comment) =>
        idsToDelete.has(comment.id),
      );

      // Check if current search query matches any comment being deleted
      const currentSearchQuery = ctx.searchQuery.value;
      const shouldClearSearch =
        currentSearchQuery.trim() && idsToDelete.has(currentSearchQuery.trim());

      // Optimistically remove comments from local state
      comments.value = originalComments.filter(
        (comment) => !idsToDelete.has(comment.id),
      );

      const response = await fetch(`/api/comments/${commentId}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        // Rollback: restore deleted comments on failure
        comments.value = originalComments;
        console.error("Failed to delete comment:", await response.text());
      } else {
        // Clear search query if it matched the deleted comment
        if (shouldClearSearch) {
          ctx.searchQuery.value = "";
        }
      }
    } catch (error) {
      console.error("Error deleting comment:", error);
      // Note: original comments should have been stored at the beginning
      // If we reach this catch block, rollback was not possible
    }
  };

  const getCommentsForHunk = (/** @type {string} */ hunkId) => {
    return comments.value.filter(
      (comment) =>
        comment.hunkId === hunkId &&
        !comment.parentId &&
        comment.lineIndex === undefined,
    );
  };

  const getCommentsForLine = (
    /** @type {string} */ hunkId,
    /** @type {number} */ lineIndex,
  ) => {
    return comments.value.filter(
      (comment) =>
        comment.hunkId === hunkId &&
        comment.lineIndex === lineIndex &&
        !comment.parentId,
    );
  };

  const getRepliesForComment = (/** @type {string} */ commentId) => {
    return comments.value.filter((comment) => comment.parentId === commentId);
  };

  const getTotalCommentsCount = () => {
    return comments.value.length;
  };

  const getTotalHunkCommentsCount = (/** @type {string} */ hunkId) => {
    return comments.value.filter((comment) => comment.hunkId === hunkId).length;
  };

  const getTotalLineCommentsCount = (
    /** @type {string} */ hunkId,
    /** @type {number} */ lineIndex,
  ) => {
    return comments.value.filter(
      (comment) => comment.hunkId === hunkId && comment.lineIndex === lineIndex,
    ).length;
  };

  return {
    comments: comments.value,
    addComment,
    deleteComment,
    getCommentsForHunk,
    getCommentsForLine,
    getRepliesForComment,
    getTotalCommentsCount,
    getTotalHunkCommentsCount,
    getTotalLineCommentsCount,
  };
}

/**
 * @param {any} props
 */
function CommentForm({
  onCancel,
  onSubmit,
  placeholder = "Add a comment...",
  selectedText,
  parentComment,
}) {
  const [commentText, setCommentText] = useState("");
  const textareaRef = useRef(/** @type {HTMLTextAreaElement | null} */ (null));

  // Auto-focus the textarea when component mounts
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);

  const handleSubmit = (/** @type {Event} */ e) => {
    e.preventDefault();
    if (commentText.trim()) {
      onSubmit(commentText);
      setCommentText(""); // Clear form after submit
    }
  };

  const handleKeyDown = (/** @type {KeyboardEvent} */ e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      handleSubmit(e);
    } else if (e.key === "Escape") {
      onCancel();
    }
  };

  return html`
    <div
      class="border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 shadow-sm"
    >
      ${selectedText &&
      html`
        <div
          class="px-4 py-2 bg-blue-50 dark:bg-blue-900/20 border-b border-blue-200 dark:border-blue-700"
        >
          <div
            class="text-xs text-blue-600 dark:text-blue-400 font-medium mb-1"
          >
            Commenting on:
          </div>
          <div
            class="font-code text-sm text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 px-2 py-1 rounded border"
          >
            "${selectedText}"
          </div>
        </div>
      `}

      <form onSubmit=${handleSubmit} class="p-4">
        <textarea
          ref=${textareaRef}
          value=${commentText}
          onInput=${(/** @type {Event} */ e) =>
            setCommentText(/** @type {HTMLTextAreaElement} */ (e.target).value)}
          onKeyDown=${handleKeyDown}
          placeholder=${placeholder}
          rows="3"
          class="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400"
        />

        <div class="flex items-center justify-between mt-3">
          <div class="text-xs text-gray-500 dark:text-gray-400">
            Press ${navigator.platform.includes("Mac") ? "⌘" : "Ctrl"}+Enter to
            submit, Esc to cancel
          </div>

          <div class="flex items-center gap-2">
            <button
              type="button"
              onClick=${onCancel}
              class="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-300 hover:text-gray-800 dark:hover:text-gray-100 transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled=${!commentText.trim()}
              class="px-4 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 disabled:cursor-not-allowed cursor-pointer transition-colors"
            >
              Comment
            </button>
          </div>
        </div>
      </form>
    </div>
  `;
}

/**
 * @param {any} props
 */
function CommentMenu({ onReply, onDelete, isOpen, onToggle }) {
  return html`
    <div class="relative">
      <button
        onClick=${onToggle}
        class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors cursor-pointer"
        aria-label="Comment actions"
      >
        <${MoreVertical} class="w-4 h-4 text-gray-400" />
      </button>

      ${isOpen &&
      html`
        <div
          class="absolute right-0 top-full mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg py-1 z-10 min-w-[120px]"
        >
          <button
            onClick=${() => {
              onReply();
              onToggle();
            }}
            class="w-full px-3 py-1.5 text-left text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2 cursor-pointer"
          >
            <${Reply} class="w-3.5 h-3.5" />
            Reply
          </button>
          <button
            onClick=${() => {
              onDelete();
              onToggle();
            }}
            class="w-full px-3 py-1.5 text-left text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2 cursor-pointer"
          >
            <${Trash2} class="w-3.5 h-3.5" />
            Delete
          </button>
        </div>
      `}
    </div>
  `;
}

/**
 * @param {any} props
 */
function CommentItem({ comment, depth = 0, onReply, onDelete }) {
  const appState = useContext(AppState);
  const { getRepliesForComment, addComment } = useComments();
  const replies = getRepliesForComment(comment.id);
  const maxDepth = 3;
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [showReplyForm, setShowReplyForm] = useState(false);

  const formatTimestamp = (/** @type {Date | string} */ timestamp) => {
    // Ensure timestamp is a Date object
    const date = timestamp instanceof Date ? timestamp : new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMinutes < 1) return "just now";
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString();
  };

  const handleReply = () => {
    setShowReplyForm(true);
  };

  const handleDelete = () => {
    onDelete(comment.id);
  };

  const handleTimestampClick = () => {
    if (appState) {
      appState.searchQuery.value = comment.id;
    }
  };

  const isRootComment = depth === 0;
  const hasReplies = replies.length > 0;
  const matchesSearch = commentMatchesSearch(
    comment,
    appState?.searchQuery.value || "",
  );

  return html`
    <div
      class="${isRootComment
        ? "border-b border-gray-100 dark:border-gray-800 pb-4 mb-4"
        : ""} ${matchesSearch
        ? "ring-2 ring-yellow-400 dark:ring-yellow-500 rounded-lg p-2 bg-yellow-50 dark:bg-yellow-900/10"
        : ""}"
    >
      <div class="flex gap-3 ${depth > 0 ? "ml-4" : ""}">
        <!-- Threading lines -->
        ${depth > 0 &&
        html`
          <div class="flex-shrink-0 w-6 flex justify-center">
            <div class="w-0.5 h-full bg-gray-200 dark:bg-gray-700 relative">
              <div
                class="absolute top-4 left-0 w-4 h-0.5 bg-gray-200 dark:bg-gray-700"
              ></div>
            </div>
          </div>
        `}

        <!-- Comment content -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <span class="font-medium text-gray-900 dark:text-gray-100 text-sm">
              ${comment.author}
            </span>
            <button
              onClick=${handleTimestampClick}
              class="text-xs text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 cursor-pointer transition-colors"
              title="Search for this comment"
            >
              ${formatTimestamp(comment.timestamp)}
            </button>
            <div class="ml-auto">
              <${CommentMenu}
                onReply=${handleReply}
                onDelete=${handleDelete}
                isOpen=${isMenuOpen}
                onToggle=${() => setIsMenuOpen(!isMenuOpen)}
              />
            </div>
          </div>

          <!-- Selected text context -->
          ${comment.selectedText &&
          html`
            <div
              class="mb-2 p-2 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded text-xs"
            >
              <div class="font-code text-gray-700 dark:text-gray-300">
                "${comment.selectedText}"
              </div>
            </div>
          `}

          <!-- Comment text -->
          <div
            class="text-gray-700 dark:text-gray-300 text-sm leading-relaxed mb-2"
          >
            <${SearchHighlight}
              text=${comment.text}
              searchQuery=${appState?.searchQuery.value || ""}
            />
          </div>
        </div>
      </div>

      <!-- Reply form -->
      ${showReplyForm &&
      html`
        <div class="mt-3 ${depth > 0 ? "ml-10" : "ml-11"}">
          <${CommentForm}
            onCancel=${() => setShowReplyForm(false)}
            onSubmit=${(/** @type {string} */ text) => {
              const formState = {
                hunkId: comment.hunkId,
                lineIndex: comment.lineIndex,
                parentId: comment.id,
              };
              addComment(formState, text);
              setShowReplyForm(false);
            }}
            placeholder="Reply to ${comment.author}..."
            parentComment=${comment}
          />
        </div>
      `}

      <!-- Replies -->
      ${hasReplies &&
      depth < maxDepth &&
      html`
        <div class="mt-3">
          ${replies.map(
            (reply) => html`
              <${CommentItem}
                key=${reply.id}
                comment=${reply}
                depth=${depth + 1}
                onReply=${onReply}
                onDelete=${onDelete}
              />
            `,
          )}
        </div>
      `}

      <!-- Show more replies if at max depth -->
      ${hasReplies &&
      depth >= maxDepth &&
      html`
        <div class="mt-2 ml-11">
          <button
            class="text-sm text-blue-600 dark:text-blue-400 hover:underline"
          >
            View ${replies.length} more
            ${replies.length === 1 ? "reply" : "replies"}
          </button>
        </div>
      `}
    </div>
  `;
}

/**
 * components
 */
/** @param {{ hunk: Hunk, hunkId: string, isCollapsed: boolean, onToggleCollapse: () => void }} props */
function HunkHeader({ hunk, hunkId, isCollapsed, onToggleCollapse }) {
  const appState = useContext(AppState);
  const { getTotalHunkCommentsCount, addComment } = useComments();
  const [showCommentForm, setShowCommentForm] = useState(false);
  const [isLinkCopied, setIsLinkCopied] = useState(false);
  const additions = hunk.lines.filter((line) => line.type === "ADD").length;
  const deletions = hunk.lines.filter((line) => line.type === "DELETE").length;
  const commentCount = getTotalHunkCommentsCount(hunkId);
  const isCompleted = hunk.completed_at != null;
  const hunkIndex = 0;
  const isCopied = false;
  const onAddComment = () => {
    setShowCommentForm(true);
  };
  const onCopy = () => {};
  const onShare = () => {};
  const diff = useDiff();
  const matchesSearch = hunkMatchesSearch(
    hunk,
    appState?.searchQuery.value || "",
  );

  const onToggleComplete = async () => {
    try {
      // Calculate the new completion state
      const newCompletedAt = hunk.completed_at
        ? null
        : new Date().toISOString();

      // Store original diff state for rollback
      const originalDiff = { ...diff.value };

      // Optimistically update the hunk completion state
      diff.value = {
        ...diff.value,
        hunks: diff.value.hunks.map((/** @type {any} */ h) =>
          h.id === hunk.id ? { ...h, completed_at: newCompletedAt } : h,
        ),
      };

      const response = await fetch(`/api/hunks/${hunk.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ completed_at: newCompletedAt }),
      });

      if (response.ok) {
        const updatedHunk = await response.json();
        // Update with server response (in case server modified the data)
        diff.value = {
          ...diff.value,
          hunks: diff.value.hunks.map((/** @type {any} */ h) =>
            h.id === hunk.id ? updatedHunk.hunk : h,
          ),
        };
      } else {
        // Rollback on failure
        diff.value = originalDiff;
        console.error(
          "Failed to toggle hunk completion:",
          await response.text(),
        );
      }
    } catch (error) {
      console.error("Failed to toggle hunk completion:", error);
      // Note: rollback should have been handled above
    }
  };

  const onRenameHunk = async (
    /** @type {string} */ hunkId,
    /** @type {string} */ newName,
  ) => {
    try {
      // Store original diff state for rollback
      const originalDiff = { ...diff.value };

      // Optimistically update the hunk name
      diff.value = {
        ...diff.value,
        hunks: diff.value.hunks.map((/** @type {Hunk} */ h) =>
          h.id === hunkId ? { ...h, name: newName } : h,
        ),
      };

      const response = await fetch(`/api/hunks/${hunkId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName }),
      });

      if (response.ok) {
        const updatedHunk = await response.json();
        // Update with server response (in case server modified the data)
        diff.value = {
          ...diff.value,
          hunks: diff.value.hunks.map((/** @type {Hunk} */ h) =>
            h.id === hunkId ? updatedHunk.hunk : h,
          ),
        };
      } else {
        // Rollback on failure
        diff.value = originalDiff;
        console.error("Failed to update hunk name:", await response.text());
      }
    } catch (error) {
      console.error("Failed to update hunk name:", error);
      // Note: rollback should have been handled above
    }
  };

  return html`
    <div
      class="px-4 py-3 bg-gray-100/50 dark:bg-gray-800/30 border-b border-gray-200/50 dark:border-gray-700/50 ${matchesSearch
        ? "ring-2 ring-yellow-400 dark:ring-yellow-500 bg-yellow-50 dark:bg-yellow-900/10"
        : ""}"
    >
      <div class="flex items-start gap-3">
        <button
          onClick=${onToggleComplete}
          class="mt-0.5 flex-shrink-0 transition-all duration-200 hover:scale-110 transform cursor-pointer"
          aria-label=${`Mark hunk ${hunkIndex + 1} as ${isCompleted ? "incomplete" : "complete"}`}
        >
          ${isCompleted
            ? html`
                <div
                  class="w-5 h-5 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shadow-sm"
                >
                  <${Check} class="w-3 h-3 text-white font-bold" />
                </div>
              `
            : html`
                <${Circle}
                  class="w-5 h-5 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                />
              `}
        </button>

        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between">
            <div class="flex-1">
              <div class=${isCompleted ? "line-through opacity-60" : ""}>
                <${HunkRename} hunk=${hunk} onRename=${onRenameHunk} />
              </div>
              <div class="flex items-center gap-3 mt-1">
                <span
                  class="font-code text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded"
                >
                  <${SearchHighlight}
                    text=${`@@ -${hunk.from_start},${hunk.from_count} +${hunk.to_start},${hunk.to_count} @@`}
                    searchQuery=${appState?.searchQuery.value || ""}
                  />
                </span>
                <div class="flex items-center gap-2 text-xs">
                  <span
                    class="text-emerald-600 dark:text-emerald-400 font-semibold bg-emerald-50 dark:bg-emerald-900/20 px-2 py-0.5 rounded-full"
                  >
                    +${additions}
                  </span>
                  <span
                    class="text-red-600 dark:text-red-400 font-semibold bg-red-50 dark:bg-red-900/20 px-2 py-0.5 rounded-full"
                  >
                    -${deletions}
                  </span>
                  ${commentCount > 0 &&
                  html`
                    <div
                      class="flex items-center gap-1 bg-blue-50 dark:bg-blue-900/20 px-2 py-1 rounded-full border border-blue-200 dark:border-blue-700 shadow-sm"
                    >
                      <${MessageSquare} class="w-3.5 h-3.5 text-blue-500" />
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
                class="p-2 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-all duration-200 group hover:scale-105 shadow-sm cursor-pointer"
                aria-label="Add comment to hunk"
                title="Add comment to hunk"
              >
                <${MessageSquare}
                  class="w-3.5 h-3.5 text-gray-400 group-hover:text-blue-500 transition-colors"
                />
              </button>
              <${CopyButton}
                text=${hunkToText(hunk)}
                ariaLabel="Copy hunk content"
                title="Copy Hunk Content"
                className="p-2 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all duration-200 group hover:scale-105 shadow-sm border border-transparent hover:border-blue-200 dark:hover:border-blue-700 cursor-pointer"
              />
              <button
                onClick=${async () => {
                  try {
                    const link = `${window.location.origin}${window.location.pathname}?search=${encodeURIComponent(hunk.id || "")}`;
                    await navigator.clipboard.writeText(link);
                    setIsLinkCopied(true);
                    setTimeout(() => setIsLinkCopied(false), 2000);
                  } catch (err) {
                    console.error("Failed to copy link:", err);
                  }
                }}
                class="p-2 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all duration-200 group hover:scale-105 shadow-sm border border-transparent hover:border-blue-200 dark:hover:border-blue-700 cursor-pointer"
                aria-label="Copy link to hunk"
                title="Copy Link to Hunk"
              >
                ${isLinkCopied
                  ? html`<${Check}
                      class="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 transition-colors"
                    />`
                  : html`<${Link}
                      class="w-3.5 h-3.5 text-gray-400 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors"
                    />`}
              </button>
              <button
                onClick=${onToggleCollapse}
                class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-all duration-200 hover:scale-105 shadow-sm cursor-pointer"
                aria-label=${`${isCollapsed ? "Expand" : "Collapse"} hunk details`}
              >
                ${isCollapsed
                  ? html`
                      <${ChevronRight}
                        class="w-3.5 h-3.5 text-gray-400 transition-transform"
                      />
                    `
                  : html`
                      <${ChevronDown}
                        class="w-3.5 h-3.5 text-gray-400 transition-transform"
                      />
                    `}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Hunk comment form -->
    ${showCommentForm &&
    html`
      <div
        class="px-4 py-3 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700"
      >
        <${CommentForm}
          onCancel=${() => setShowCommentForm(false)}
          onSubmit=${(/** @type {string} */ text) => {
            const formState = { hunkId: hunkId };
            addComment(formState, text);
            setShowCommentForm(false);
          }}
          placeholder="Comment on this hunk..."
        />
      </div>
    `}
  `;
}

/** @param {any} props */
function Line({ line, hunkId, lineIndex }) {
  const appState = useContext(AppState);
  const {
    getCommentsForLine,
    addComment,
    deleteComment,
    getTotalLineCommentsCount,
  } = useComments();
  const [showCommentForm, setShowCommentForm] = useState(false);
  const lineComments = getCommentsForLine(hunkId, lineIndex);
  const totalComments = getTotalLineCommentsCount(hunkId, lineIndex);

  /** @param {Number} number */
  const renderLineNumber = (number) => {
    return number
      ? html`<span
          class="text-gray-500 dark:text-gray-400 select-none font-medium"
          >${number}</span
        >`
      : html`<span
          class="text-gray-500 dark:text-gray-400 select-none font-medium opacity-50"
          >·</span
        >`;
  };

  /**
   * @param {any} type
   */
  const getLineStyles = (type) => {
    const searchQuery = appState?.searchQuery.value || "";
    const isHighlighted =
      searchQuery.trim() && line.id.toLowerCase() === searchQuery.toLowerCase();

    let baseClasses;
    switch (type) {
      case "ADD":
        baseClasses = "diff-add border-l-2 transition-diff cursor-pointer";
        break;
      case "DELETE":
        baseClasses = "diff-remove border-l-2 transition-diff cursor-pointer";
        break;
      case "CONTEXT":
        baseClasses =
          "diff-context border-l-2 border-transparent transition-diff cursor-pointer";
        break;
      default:
        baseClasses =
          "diff-context border-l-2 border-transparent transition-diff cursor-pointer";
        break;
    }

    // Add highlighting classes if line ID matches search query
    if (isHighlighted) {
      baseClasses +=
        " bg-yellow-100 dark:bg-yellow-900/30 ring-2 ring-yellow-300 dark:ring-yellow-700/50";
    }

    return baseClasses;
  };

  const handleLineClick = () => {
    setShowCommentForm(true);
  };

  /**
   * @param {any} type
   */
  function getLineIcon(type) {
    switch (type) {
      case "ADD":
        return html`<span
          class="font-bold"
          style="color: hsl(var(--diff-add-border))"
          >+</span
        >`;
      case "DELETE":
        return html`<span
          class="font-bold"
          style="color: hsl(var(--diff-remove-border))"
          >-</span
        >`;
      default:
        return html`<span class="text-gray-400 dark:text-gray-600"> </span>`;
    }
  }

  const showLineCommentForm = showCommentForm;

  return html`
    <div>
      <div
        class=${`flex ${getLineStyles(line.type)} group relative`}
        onClick=${handleLineClick}
      >
        <div
          class="w-10 px-2 py-1 text-right text-xs font-code border-r border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/50"
        >
          ${renderLineNumber(line.line_number_old)}
        </div>
        <div
          class="w-10 px-2 py-1 text-right text-xs font-code border-r border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/50"
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
          <${SearchHighlight}
            text=${line.content}
            searchQuery=${appState?.searchQuery.value || ""}
          />
        </div>

        <div class="w-28 px-2 py-1 flex items-center justify-end gap-1">
          ${totalComments > 0 &&
          html`<div
            class="w-4 h-4 rounded-full bg-blue-500 dark:bg-blue-600 flex items-center justify-center shadow-sm flex-shrink-0"
          >
            <span class="text-xs text-white font-semibold">
              ${totalComments}
            </span>
          </div>`}
          <div
            class="opacity-0 group-hover:opacity-100 transition-all duration-200 flex gap-0.5"
          >
            <${CopyButton}
              text=${line.content}
              ariaLabel="Copy line content"
              title="Copy Line Content"
              className="p-0.5 rounded-md hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all duration-200 border border-transparent hover:border-blue-200 dark:hover:border-blue-700 cursor-pointer"
            />
            <${CopyLinkButton}
              lineId=${line.id}
              ariaLabel="Copy link to line"
              title="Copy Link to Line"
              className="p-0.5 rounded-md hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all duration-200 border border-transparent hover:border-blue-200 dark:hover:border-blue-700 cursor-pointer"
            />
            <button
              onClick=${() => setShowCommentForm(true)}
              class="p-0.5 rounded-md hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all duration-200 border border-transparent hover:border-blue-200 dark:hover:border-blue-700 cursor-pointer"
              aria-label="Add comment to line"
              title="Add Comment to Line"
            >
              <${MessageSquare}
                class="w-3.5 h-3.5 text-gray-400 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors"
              />
            </button>
          </div>
        </div>
        <div
          class="absolute inset-0 opacity-0 group-hover:opacity-5 bg-blue-500 transition-opacity duration-200 pointer-events-none"
        />
      </div>

      <!-- Line comment form -->
      ${showLineCommentForm &&
      html`
        <div
          class="px-4 py-3 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700"
        >
          <${CommentForm}
            onCancel=${() => {
              setShowCommentForm(false);
            }}
            onSubmit=${(/** @type {string} */ text) => {
              const formState = {
                hunkId: hunkId,
                lineIndex: lineIndex,
              };
              addComment(formState, text);
              setShowCommentForm(false);
            }}
            placeholder="Comment on this line..."
          />
        </div>
      `}

      <!-- Line comments -->
      ${lineComments.length > 0 &&
      html`
        <div
          class="px-4 py-3 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700"
        >
          <div class="space-y-3">
            ${lineComments.map(
              (
                /** @type {Comment} */ comment,
                /** @type {number} */ index,
              ) => html`
                <${CommentItem}
                  key=${comment.id}
                  comment=${comment}
                  onReply=${(/** @type {Comment} */ replyToComment) => {
                    setShowCommentForm(true);
                  }}
                  onDelete=${(/** @type {string} */ commentId) => {
                    deleteComment(commentId);
                  }}
                />
              `,
            )}
          </div>
        </div>
      `}
    </div>
  `;
}

/**
 * @param {any} props
 */
function Hunk({ hunk, hunkIndex }) {
  const hunkId = `hunk-${hunkIndex}`;
  const { getCommentsForHunk, deleteComment } = useComments();
  const hunkComments = getCommentsForHunk(hunkId);
  const appState = useContext(AppState);
  if (!appState) throw new Error("Hunk must be used within AppState");

  const isCollapsed = appState.collapsedHunks.value.has(hunkIndex);
  const isCompleted = hunk.completed_at != null;

  const handleToggleCollapse = () => {
    const newCollapsed = new Set(appState.collapsedHunks.value);
    if (newCollapsed.has(hunkIndex)) {
      newCollapsed.delete(hunkIndex);
    } else {
      newCollapsed.add(hunkIndex);
    }
    appState.collapsedHunks.value = newCollapsed;
  };

  return html`
    <div
      class="dark:bg-monokai-bg transition-all duration-300 ${isCompleted
        ? "opacity-75"
        : ""}"
    >
      <!-- hunk header -->
      <${HunkHeader}
        hunk=${hunk}
        hunkId=${hunkId}
        isCollapsed=${isCollapsed}
        onToggleCollapse=${handleToggleCollapse}
      />

      <!-- hunk body - simple conditional rendering like original -->
      ${!isCollapsed &&
      html`
        <div
          class="font-code text-sm border-t border-gray-200/50 dark:border-monokai-border/50"
        >
          <!-- lines -->
          ${hunk.lines.map(
            /** @param {any} line */
            (line, /** @type {number} */ lineIndex) =>
              html`<${Line}
                line=${line}
                hunkId=${hunkId}
                lineIndex=${lineIndex}
              />`,
          )}
        </div>

        <!-- Hunk-level comments -->
        ${hunkComments.length > 0 &&
        html`
          <div
            class="px-4 py-3 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700"
          >
            <div class="space-y-3">
              ${hunkComments.map(
                (
                  /** @type {Comment} */ comment,
                  /** @type {number} */ index,
                ) => html`
                  <${CommentItem}
                    key=${comment.id}
                    comment=${comment}
                    onReply=${(/** @type {Comment} */ replyToComment) => {
                      // Reply functionality handled by CommentItem internally
                    }}
                    onDelete=${(/** @type {string} */ commentId) => {
                      deleteComment(commentId);
                    }}
                  />
                `,
              )}
            </div>
          </div>
        `}
      `}
    </div>
  `;
}

/**
 * FileRename component
 */
function FileRename() {
  const appState = useContext(AppState);
  if (!appState) throw new Error("FileRename must be used within AppState");
  const { diff, isEditing, editValue } = appState;
  const inputRef = useRef(/** @type {HTMLInputElement | null} */ (null));

  const validateName = (/** @type {string} */ name) => name.trim().length > 0;
  const isValid = () => validateName(editValue.value);

  const handleEdit = () => {
    editValue.value = diff.value.name || diff.value.id;
    isEditing.value = true;
  };

  // Auto-focus and select text when entering edit mode
  useEffect(() => {
    if (isEditing.value && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing.value]);

  const handleSave = async () => {
    const trimmedValue = editValue.value.trim();
    if (!validateName(trimmedValue) || trimmedValue === diff.value.name) {
      isEditing.value = false;
      return;
    }

    try {
      // Store original diff state for rollback
      const originalDiff = { ...diff.value };

      // Optimistically update the diff name
      diff.value = { ...diff.value, name: trimmedValue };
      isEditing.value = false;

      const response = await fetch(`/api/diffs/${diff.value.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmedValue }),
      });

      if (response.ok) {
        const updatedDiff = await response.json();
        diff.value = updatedDiff.diff;
      } else {
        // Rollback on failure
        diff.value = originalDiff;
        isEditing.value = true; // Re-enter editing mode on failure
        console.error("Failed to update diff name:", await response.text());
      }
    } catch (error) {
      console.error("Failed to update diff name:", error);
      // Note: rollback should have been handled above
    }
  };

  const handleCancel = () => {
    editValue.value = diff.value.name || diff.value.id;
    isEditing.value = false;
  };

  const handleKeyDown = (/** @type {KeyboardEvent} */ e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      handleCancel();
    }
  };

  const handleChange = (/** @type {Event} */ e) => {
    const target = /** @type {HTMLInputElement} */ (e.target);
    editValue.value = target.value;
  };

  const handleSubmit = (/** @type {Event} */ e) => {
    e.preventDefault();
    if (isValid()) handleSave();
  };

  if (isEditing.value) {
    return html`
      <form onSubmit=${handleSubmit} class="flex items-center gap-2">
        <div class="flex-1 relative">
          <input
            ref=${inputRef}
            type="text"
            value=${editValue.value}
            onChange=${handleChange}
            onKeyDown=${handleKeyDown}
            class="w-full px-2 py-1 text-lg font-code font-semibold bg-white dark:bg-monokai-surface border rounded-md focus:outline-none focus:ring-2 transition-colors ${isValid()
              ? "border-gray-300 dark:border-monokai-border focus:ring-blue-500 text-gray-900 dark:text-monokai-text"
              : "border-red-300 dark:border-red-600 focus:ring-red-500 text-red-700 dark:text-red-400"}"
            placeholder="Enter file name..."
          />
          ${!isValid() &&
          html`
            <div
              class="absolute top-full left-0 mt-1 px-2 py-1 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded text-xs text-red-600 dark:text-red-400 whitespace-nowrap"
            >
              Name cannot be empty
            </div>
          `}
        </div>
        <button
          type="submit"
          disabled=${!isValid() || editValue.value.trim() === diff.value.name}
          class="p-1.5 rounded-md hover:bg-emerald-100 dark:hover:bg-emerald-900/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Save file name"
          title="Save (Enter)"
        >
          <${Check} class="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
        </button>
        <button
          onClick=${handleCancel}
          class="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          aria-label="Cancel rename"
          title="Cancel (Esc)"
          type="button"
        >
          <${X} class="w-4 h-4 text-gray-500 dark:text-gray-400" />
        </button>
      </form>
    `;
  }

  return html`
    <div class="flex items-center gap-2 group">
      <h1
        onClick=${handleEdit}
        class="text-lg font-code font-semibold text-gray-900 dark:text-monokai-text tracking-tight cursor-pointer hover:text-gray-700 dark:hover:text-monokai-text"
        title="Click to rename file"
      >
        ${diff.value.name || diff.value.id}
      </h1>
      <button
        onClick=${handleEdit}
        class="opacity-0 group-hover:opacity-100 p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-monokai-elevated transition-all duration-200 hover:scale-105"
        aria-label="Rename file"
        title="Rename file"
      >
        <${Edit3}
          class="w-3.5 h-3.5 text-gray-400 dark:text-monokai-muted hover:text-gray-600 dark:hover:text-monokai-text"
        />
      </button>
    </div>
  `;
}

function FileHeader() {
  const diff = useDiff();
  const appState = useContext(AppState);
  if (!appState) throw new Error("FileHeader must be used within AppState");
  const [isFileLinkCopied, setIsFileLinkCopied] = useState(false);

  // Calculate completion statistics
  const completedCount = diff.value.hunks.filter(
    (hunk) => hunk.completed_at != null,
  ).length;
  const totalCount = diff.value.hunks.length;
  const uncompletedCount = totalCount - completedCount;
  const isAllCompleted = totalCount > 0 && completedCount === totalCount;
  const totalAdditions = diff.value.hunks.reduce(
    (sum, hunk) =>
      sum + hunk.lines.filter((line) => line.type === "ADD").length,
    0,
  );
  const totalDeletions = diff.value.hunks.reduce(
    (sum, hunk) =>
      sum + hunk.lines.filter((line) => line.type === "DELETE").length,
    0,
  );

  // Filter hunks for bulk operations based on current filter
  const visibleHunks = diff.value.hunks.filter((hunk) => {
    const isCompleted = hunk.completed_at != null;
    switch (appState.currentFilter.value) {
      case "completed":
        return isCompleted;
      case "uncompleted":
        return !isCompleted;
      case "all":
      default:
        return true;
    }
  });

  // Calculate if all visible hunks are collapsed
  const allVisibleHunksCollapsed =
    visibleHunks.length > 0 &&
    visibleHunks.every((hunk) => {
      const originalIndex = diff.value.hunks.findIndex((h) => h.id === hunk.id);
      return appState.collapsedHunks.value.has(originalIndex);
    });

  // Toggle all visible hunks expand/collapse
  const toggleAllHunks = () => {
    const newCollapsed = new Set(appState.collapsedHunks.value);
    const visibleHunkIndices = visibleHunks.map((hunk) =>
      diff.value.hunks.findIndex((h) => h.id === hunk.id),
    );

    if (allVisibleHunksCollapsed) {
      // Expand all visible hunks
      visibleHunkIndices.forEach((index) => {
        newCollapsed.delete(index);
      });
    } else {
      // Collapse all visible hunks
      visibleHunkIndices.forEach((index) => {
        newCollapsed.add(index);
      });
    }

    appState.collapsedHunks.value = newCollapsed;
  };

  return html`
    <div
      class="px-4 py-4 border-b border-gray-200 dark:border-monokai-border bg-gradient-to-r from-white to-gray-50/50 dark:from-monokai-bg dark:to-monokai-surface/50"
    >
      <div class="flex items-center justify-between mb-4">
        <div class="flex-1">
          <div class="flex items-center gap-4 mb-3">
            <${FileRename} />
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
                ${diff.value.from_timestamp &&
                html`
                  <span class="text-gray-500 dark:text-gray-400 text-xs ml-2">
                    ${diff.value.from_timestamp.toLocaleString()}
                  </span>
                `}
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
                ${diff.value.to_timestamp &&
                html`
                  <span class="text-gray-500 dark:text-gray-400 text-xs ml-2">
                    ${diff.value.to_timestamp.toLocaleString()}
                  </span>
                `}
              </div>
            `}
          </div>

          <!-- Completion statistics -->
          <div class="flex items-center gap-4 text-xs">
            <div class="flex items-center gap-2">
              ${isAllCompleted
                ? html`
                    <div
                      class="w-4 h-4 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shadow-sm transition-all duration-500"
                    >
                      <${Check} class="w-2.5 h-2.5 text-white font-bold" />
                    </div>
                  `
                : html`
                    <div
                      class="w-4 h-4 rounded-full bg-gray-200 dark:bg-monokai-elevated flex items-center justify-center shadow-inner"
                    >
                      <div
                        class="w-2.5 h-2.5 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 transition-all duration-500 shadow-sm"
                        style="transform: scale(${totalCount > 0
                          ? completedCount / totalCount
                          : 0})"
                      />
                    </div>
                  `}
              <span class="text-gray-600 dark:text-monokai-muted">
                ${completedCount} of ${totalCount} completed
              </span>
            </div>
            <div class="flex items-center gap-2">
              <span
                class="text-emerald-600 dark:text-emerald-400 font-semibold bg-emerald-50 dark:bg-emerald-900/20 px-2 py-0.5 rounded-full"
              >
                +${totalAdditions}
              </span>
              <span
                class="text-red-600 dark:text-red-400 font-semibold bg-red-50 dark:bg-red-900/20 px-2 py-0.5 rounded-full"
              >
                -${totalDeletions}
              </span>
            </div>
          </div>
        </div>

        <!-- Right side controls -->
        <div class="flex items-center gap-1">
          <${CopyButton}
            text=${diff.value.raw}
            ariaLabel="Copy diff content"
            title="Copy Diff Content"
            className="p-2 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all duration-200 group hover:scale-105 shadow-sm border border-transparent hover:border-blue-200 dark:hover:border-blue-700 cursor-pointer"
          />
          <button
            onClick=${async () => {
              try {
                const link = `${window.location.origin}${window.location.pathname}`;
                await navigator.clipboard.writeText(link);
                setIsFileLinkCopied(true);
                setTimeout(() => setIsFileLinkCopied(false), 2000);
              } catch (err) {
                console.error("Failed to copy link:", err);
              }
            }}
            class="p-2 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all duration-200 group hover:scale-105 shadow-sm border border-transparent hover:border-blue-200 dark:hover:border-blue-700 cursor-pointer"
            aria-label="Copy link to file"
            title="Copy Link to File"
          >
            ${isFileLinkCopied
              ? html`<${Check}
                  class="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 transition-colors"
                />`
              : html`<${Link}
                  class="w-3.5 h-3.5 text-gray-400 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors"
                />`}
          </button>
          <button
            onClick=${toggleAllHunks}
            class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-all duration-200 group hover:scale-105 shadow-sm cursor-pointer"
            aria-label=${allVisibleHunksCollapsed
              ? "Expand all hunks"
              : "Collapse all hunks"}
            title=${allVisibleHunksCollapsed
              ? "Expand all hunks"
              : "Collapse all hunks"}
          >
            ${allVisibleHunksCollapsed
              ? html`
                  <${ChevronRight}
                    class="w-3.5 h-3.5 text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300 transition-colors"
                  />
                `
              : html`
                  <${ChevronDown}
                    class="w-3.5 h-3.5 text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300 transition-colors"
                  />
                `}
          </button>
        </div>
      </div>

      <!-- search wrapper -->
      <div class="flex items-center gap-4">
        <${SearchBar}
          searchQuery=${appState.searchQuery.value}
          onSearchChange=${(/** @type {string} */ query) => {
            appState.searchQuery.value = query;
          }}
          resultCount=${diff.value.hunks.filter((hunk, index) =>
            searchInHunk(
              hunk,
              appState.searchQuery.value,
              appState.comments.value,
              index,
            ),
          ).length}
          totalHunks=${diff.value.hunks.length}
          isSearching=${appState.searchQuery.value !==
          appState.searchQuery.value}
        />
        <${HunkFilter}
          currentFilter=${appState.currentFilter.value}
          onFilterChange=${(/** @type {FilterType} */ filter) => {
            appState.currentFilter.value = filter;
          }}
          completedCount=${completedCount}
          uncompletedCount=${uncompletedCount}
          totalCount=${totalCount}
        />
      </div>

      <!-- next -->
    </div>
  `;
}

/**
 * Search helper function to check if hunk matches search query
 * Searches in hunk ID, name, header, line content, line IDs, and comments
 * @param {Hunk} hunk - The hunk to search
 * @param {string} query - The search query
 * @param {Comment[]} comments - All comments for the diff
 * @param {number} hunkIndex - The hunk's index in the diff
 * @returns {boolean} - Whether the hunk matches the search
 */
function searchInHunk(hunk, query, comments, hunkIndex) {
  if (!query.trim()) return true;
  const searchTerm = query.toLowerCase();

  // Search in hunk ID
  if (hunk.id && hunk.id.toLowerCase().includes(searchTerm)) return true;

  // Search in hunk name
  if (hunk.name && hunk.name.toLowerCase().includes(searchTerm)) return true;

  // Create hunk header for search (like "@@ -1,7 +1,7 @@")
  const header = `@@ -${hunk.from_start},${hunk.from_count} +${hunk.to_start},${hunk.to_count} @@`;
  if (header.toLowerCase().includes(searchTerm)) return true;

  // Search in line content and line IDs
  if (
    hunk.lines.some(
      (line) =>
        line.content.toLowerCase().includes(searchTerm) ||
        (line.id && line.id.toLowerCase().includes(searchTerm)),
    )
  ) {
    return true;
  }

  // Search in comments for this hunk
  const hunkComments = comments.filter(
    (comment) => comment.hunkId === `hunk-${hunkIndex}`,
  );
  if (
    hunkComments.some(
      (comment) =>
        comment.text.toLowerCase().includes(searchTerm) ||
        comment.author.toLowerCase().includes(searchTerm) ||
        comment.id.toLowerCase().includes(searchTerm),
    )
  ) {
    return true;
  }

  return false;
}

/**
 * Check if a comment ID matches the search query
 * @param {Comment} comment - The comment to check
 * @param {string} query - The search query
 * @returns {boolean} - Whether the comment ID matches the search
 */
function commentMatchesSearch(comment, query) {
  if (!query.trim()) return false;
  const searchTerm = query.toLowerCase();

  return comment.id.toLowerCase() === searchTerm;
}

/**
 * Check if a hunk ID matches the search query
 * @param {Hunk} hunk - The hunk to check
 * @param {string} query - The search query
 * @returns {boolean} - Whether the hunk ID matches the search
 */
function hunkMatchesSearch(hunk, query) {
  if (!query.trim()) return false;
  const searchTerm = query.toLowerCase();

  return !!(hunk.id && hunk.id.toLowerCase() === searchTerm);
}

function App() {
  const diff = useDiff();
  const appState = useContext(AppState);
  if (!appState) throw new Error("App must be used within AppState");

  // Sync search query with URL parameter
  useEffect(() => {
    updateURLParameter("search", appState.searchQuery.value);
  }, [appState.searchQuery.value]);

  // Filter hunks based on current filter and search
  const filteredHunks = diff.value.hunks.filter((hunk, index) => {
    const isCompleted = hunk.completed_at != null;

    // Apply completion filter
    let passesFilter = true;
    switch (appState.currentFilter.value) {
      case "completed":
        passesFilter = isCompleted;
        break;
      case "uncompleted":
        passesFilter = !isCompleted;
        break;
      case "all":
      default:
        passesFilter = true;
        break;
    }

    // Apply search filter
    const passesSearch = searchInHunk(
      hunk,
      appState.searchQuery.value,
      appState.comments.value,
      index,
    );

    return passesFilter && passesSearch;
  });

  return html`
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
            ${filteredHunks.length === 0
              ? html`
                  <div class="p-8 text-center">
                    <div class="text-gray-500 dark:text-monokai-muted">
                      <div class="text-lg font-medium mb-2">
                        No hunks match the current filter
                      </div>
                      <div class="text-sm">
                        ${appState.currentFilter.value === "completed" &&
                        "No hunks have been completed yet."}
                        ${appState.currentFilter.value === "uncompleted" &&
                        "All hunks have been completed!"}
                      </div>
                    </div>
                  </div>
                `
              : filteredHunks.map(
                  /** @param {any} hunk */
                  (hunk) => {
                    // Find the original index for collapsed state management
                    const originalIndex = diff.value.hunks.findIndex(
                      (h) => h.id === hunk.id,
                    );
                    return html`
                      <${Hunk} hunk=${hunk} hunkIndex=${originalIndex} />
                    `;
                  },
                )}
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Update document title based on diff name and completion status
 */
function updateDocumentTitle(/** @type {Diff} */ diff) {
  const diffName = diff.name || "diffswarm";
  const completedCount = diff.hunks.filter(
    (hunk) => hunk.completed_at != null,
  ).length;
  const totalCount = diff.hunks.length;
  const isAllCompleted = totalCount > 0 && completedCount === totalCount;

  if (totalCount > 0 && diffName !== "diffswarm") {
    const completionPrefix = isAllCompleted ? "✅ " : "";
    document.title = `${completionPrefix}[${completedCount}/${totalCount}] ${diffName}`;
  } else {
    document.title = diffName;
  }
}

/**
 * set up and mount the app
 */
const appState = createAppState();

// Initial title update
updateDocumentTitle(appState.diff.value);

// Watch for changes to diff and update title
appState.diff.subscribe((diff) => {
  updateDocumentTitle(diff);
});

render(
  html`
    <${AppState.Provider} value=${appState}>
      <${App} />
    <//>
  `,
  $APP,
);
