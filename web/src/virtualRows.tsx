// Long lists draw only the rows in view (ticket 0374, spec §11). Rows have the height they have: each is measured once drawn, and
// until then it counts as `estimate`. The scrolling ancestor is found, not given, so the list sits wherever its screen puts it.

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from "react";

const OVERSCAN_PX = 240;

function scrollerOf(node: HTMLElement): HTMLElement {
  for (let at = node.parentElement; at; at = at.parentElement) {
    const overflow = getComputedStyle(at).overflowY;
    if (overflow === "auto" || overflow === "scroll") return at;
  }
  return document.documentElement;
}

export function VirtualRows<T>(props: {
  items: T[];
  keyOf: (item: T) => string;
  estimate: number;
  render: (item: T) => ReactNode;
  onRange?: (items: T[]) => void; // the items now drawn, for the caller to ask what they need
  testid?: string;
}) {
  const { items, keyOf, estimate, render, onRange } = props;
  const host = useRef<HTMLDivElement>(null);
  const heights = useRef(new Map<string, number>());
  const [, measured] = useState(0);
  const [view, setView] = useState({ top: 0, height: 900 });
  const watcher = useRef<ResizeObserver | null>(null);
  const frame = useRef(0);

  const place = useCallback(() => {
    const node = host.current;
    if (!node) return;
    const scroller = scrollerOf(node);
    const scrolling = scroller === document.documentElement;
    const own = scrolling ? node.getBoundingClientRect().top + window.scrollY : node.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop;
    const top = (scrolling ? window.scrollY : scroller.scrollTop) - own;
    const height = scrolling ? window.innerHeight : scroller.clientHeight;
    setView((before) => (Math.abs(before.top - top) < 1 && before.height === height ? before : { top, height }));
  }, []);

  useLayoutEffect(() => {
    const node = host.current;
    if (!node) return;
    const scroller = scrollerOf(node);
    place();
    const target: EventTarget = scroller === document.documentElement ? window : scroller;
    target.addEventListener("scroll", place, { passive: true });
    window.addEventListener("resize", place);
    const sizes = new ResizeObserver(place);
    sizes.observe(scroller);
    return () => {
      target.removeEventListener("scroll", place);
      window.removeEventListener("resize", place);
      sizes.disconnect();
    };
  }, [place]);

  const getWatcher = useCallback((): ResizeObserver => {
    if (!watcher.current) {
      watcher.current = new ResizeObserver((entries) => {
        let changed = false;
        for (const entry of entries) {
          const target = entry.target as HTMLElement;
          if (!target.isConnected) {
            watcher.current?.unobserve(target);
            continue;
          }
          const key = target.dataset.rowKey;
          const height = Math.ceil(target.getBoundingClientRect().height);
          if (key && height > 0 && heights.current.get(key) !== height) {
            heights.current.set(key, height);
            changed = true;
          }
        }
        if (changed && !frame.current) {
          frame.current = requestAnimationFrame(() => {
            frame.current = 0;
            measured((count) => count + 1);
            place();
          });
        }
      });
    }
    return watcher.current;
  }, [place]);
  useEffect(
    () => () => {
      watcher.current?.disconnect();
      watcher.current = null;
      if (frame.current) cancelAnimationFrame(frame.current);
    },
    [],
  );

  const offsets: number[] = new Array(items.length + 1);
  offsets[0] = 0;
  items.forEach((item, at) => {
    offsets[at + 1] = offsets[at] + (heights.current.get(keyOf(item)) ?? estimate);
  });
  const total = offsets[items.length];
  const from = view.top - OVERSCAN_PX;
  const to = view.top + view.height + OVERSCAN_PX;
  let start = 0;
  while (start < items.length && offsets[start + 1] < from) start += 1;
  let end = start;
  while (end < items.length && offsets[end] <= to) end += 1;
  const shown = items.slice(start, end);

  const range = shown.map(keyOf).join("\n");
  const asked = useRef("");
  const report = useRef(onRange);
  report.current = onRange;
  useEffect(() => {
    if (asked.current === range) return;
    asked.current = range;
    report.current?.(shown);
  });

  const measure = useCallback(
    (node: HTMLDivElement | null) => {
      if (node) getWatcher().observe(node);
    },
    [getWatcher],
  );

  return (
    <div ref={host} className="virtual-rows" data-testid={props.testid} style={{ height: total, position: "relative" }}>
      {shown.map((item, at) => {
        const key = keyOf(item);
        return (
          <div key={key} ref={measure} data-row-key={key} style={{ left: 0, position: "absolute", right: 0, top: offsets[start + at] }}>
            {render(item)}
          </div>
        );
      })}
    </div>
  );
}

// Whether a node is in view: a section that draws, or asks, only then (ticket 0374).
export function useInView(node: RefObject<HTMLElement | null>): boolean {
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const target = node.current;
    if (!target) return;
    const watch = new IntersectionObserver((entries) => setSeen(entries.some((entry) => entry.isIntersecting)));
    watch.observe(target);
    return () => watch.disconnect();
  }, [node]);
  return seen;
}
