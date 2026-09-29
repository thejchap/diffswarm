// @ts-check
import { signal } from "@preact/signals";

export const viewportWidth = signal(document.documentElement.clientWidth);
/** @type {Map<Element, (visible: boolean) => void>} */
const visibilityCallbacks = new Map();
/** @type {Map<Element, (height: number) => void>} */
const resizeCallbacks = new Map();
const intersectionObserver = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      visibilityCallbacks.get(entry.target)?.(entry.isIntersecting);
    }
  },
  { rootMargin: "200px" },
);
const resizeObserver = new ResizeObserver((entries) => {
  viewportWidth.value = document.documentElement.clientWidth;
  for (const entry of entries) {
    resizeCallbacks.get(entry.target)?.(entry.contentRect.height);
  }
});
resizeObserver.observe(document.documentElement);

/** @param {Element} element @param {(visible: boolean) => void} onVisibility */
export function observeHunk(element, onVisibility) {
  visibilityCallbacks.set(element, onVisibility);
  intersectionObserver.observe(element);
  return () => {
    intersectionObserver.unobserve(element);
    visibilityCallbacks.delete(element);
  };
}

/** @param {Element} element @param {(height: number) => void} onResize */
export function measureHunk(element, onResize) {
  resizeCallbacks.set(element, onResize);
  resizeObserver.observe(element);
  return () => {
    resizeObserver.unobserve(element);
    resizeCallbacks.delete(element);
  };
}
