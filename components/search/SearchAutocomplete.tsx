"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { MagnifyingGlass, X } from "@phosphor-icons/react/dist/ssr";

import { comboKeyAction } from "./search-combobox-model";

/**
 * The search field, with product suggestions.
 *
 * Three QA findings shaped this:
 *
 * QA-008 — a partial query surfaced a useful match but there was no way to act
 * on it. Suggestions are now selectable, by pointer or keyboard, and selecting
 * one runs the search for that product rather than leaving the reader to retype
 * it.
 *
 * QA-009 — the results had no interactive treatment. Options carry a pointer
 * cursor, a hover and an active-descendant highlight, and `aria-selected`, so
 * the highlighted row is the same row Enter will choose.
 *
 * QA-010 — suggestions appeared for an empty field. Nothing is requested until
 * the query has `MIN_QUERY` non-whitespace characters, and clearing the input
 * drops the list immediately rather than leaving the previous one on screen.
 *
 * It stays a real `<form action="/search">`: with JavaScript unavailable, or
 * before hydration, submitting still searches. The listbox is an enhancement on
 * top of that, not a replacement for it.
 */

const MIN_QUERY = 2;
const DEBOUNCE_MS = 250;

type Suggestion = { id: string; canonical_name: string | null; category: string | null };

export function SearchAutocomplete({
  defaultValue = "",
  placeholder = "Search or ask anything",
  inputClassName,
  showClear = false,
}: {
  defaultValue?: string;
  placeholder?: string;
  inputClassName: string;
  showClear?: boolean;
}) {
  const router = useRouter();
  const listId = useId();
  const [query, setQuery] = useState(defaultValue);
  // Results are stored WITH the query that produced them, and the highlight
  // with the query it belongs to. Both are then derived rather than cleared
  // from an effect — clearing state inside an effect schedules a cascading
  // render, which this project lints against, and deriving is also what makes
  // a stale list impossible rather than merely unlikely.
  const [result, setResult] = useState<{ q: string; items: Suggestion[] }>({
    q: "",
    items: [],
  });
  const [highlight, setHighlight] = useState<{ q: string; i: number }>({ q: "", i: -1 });
  // Start dismissed when the field arrives pre-filled from `?q=`.
  //
  // Otherwise /search?q=jisulife mounts with an eligible query, fetches, and
  // drops a suggestion list over the results the reader just asked for —
  // covering the tabs and the first rows before they have touched anything.
  // Suggestions are for a query being typed; a query that came from the URL has
  // already been submitted. Typing, or ArrowDown, opens the list as usual.
  const [dismissed, setDismissed] = useState(defaultValue.trim().length > 0);
  const rootRef = useRef<HTMLDivElement | null>(null);

  const trimmed = query.trim();
  const eligible = trimmed.length >= MIN_QUERY;
  // QA-010: below the threshold there is nothing to show, whatever was fetched
  // for a previous query. An emptied field therefore shows nothing at once.
  const items = eligible && result.q === trimmed ? result.items : [];
  const active = highlight.q === trimmed && highlight.i < items.length ? highlight.i : -1;
  const open = !dismissed && items.length > 0;

  const setActive = (i: number) => setHighlight({ q: trimmed, i });

  useEffect(() => {
    // Nothing is requested below the threshold; the list is already empty by
    // derivation above, so there is no state to clear here.
    if (!eligible) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(
          `/api/bff/api/v1/products?q=${encodeURIComponent(trimmed)}&limit=6`,
        );
        if (!res.ok) throw new Error(String(res.status));
        const data = (await res.json()) as Suggestion[];
        if (cancelled) return;
        setResult({ q: trimmed, items: Array.isArray(data) ? data : [] });
      } catch {
        if (!cancelled) setResult({ q: trimmed, items: [] });
      }
    }, DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [trimmed, eligible]);

  // A click outside closes the list without clearing what was typed.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setDismissed(true);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [open]);

  function choose(s: Suggestion) {
    const name = s.canonical_name?.trim();
    if (!name) return;
    setQuery(name);
    setDismissed(true);
    router.push(`/search?q=${encodeURIComponent(name)}`);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    // The decision lives in `comboKeyAction` so it can be tested without a DOM.
    // In particular `preventDefault` on Escape is load-bearing: `type="search"`
    // clears itself otherwise, which wiped the query the dismissal was meant to
    // keep. See that module for why.
    const action = comboKeyAction(e.key, {
      open,
      dismissed,
      eligible,
      itemCount: items.length,
      active,
    });
    if (action.preventDefault) e.preventDefault();
    switch (action.type) {
      case "dismiss":
        setDismissed(true);
        break;
      case "reopen":
        setDismissed(false);
        // Highlight the first option as the list comes back, per the ARIA
        // combobox pattern — otherwise the list is visible with nothing current.
        if (action.to !== null) setActive(action.to);
        break;
      case "move":
        setActive(action.to);
        break;
      case "choose":
        choose(items[action.index]);
        break;
      default:
        break;
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <form action="/search" role="search" className="relative">
        <MagnifyingGlass
          size={20}
          className="pointer-events-none absolute left-5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
        />
        <input
          type="search"
          name="q"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setDismissed(false);
          }}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          aria-label="Search"
          role="combobox"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-autocomplete="list"
          aria-activedescendant={
            open && active >= 0 ? `${listId}-${active}` : undefined
          }
          className={inputClassName}
        />
        {showClear && query ? (
          <button
            type="button"
            aria-label="Clear search"
            onClick={() => {
              setQuery("");
              // The field is not the only thing showing the query: the results
              // below are server-rendered from `?q=`. Clearing only local state
              // left an empty box above a full result list, and a reload
              // brought the query back.
              if (new URLSearchParams(window.location.search).get("q")) {
                router.push("/search");
              }
            }}
            className="absolute right-3 top-1/2 grid h-9 w-9 -translate-y-1/2 cursor-pointer place-items-center rounded-full text-[var(--text-secondary)] hover:bg-[var(--line-hairline-10)]"
          >
            <X size={20} />
          </button>
        ) : null}
      </form>

      {open ? (
        <ul
          id={listId}
          role="listbox"
          aria-label="Product suggestions"
          className="absolute inset-x-0 top-[calc(100%+0.35rem)] z-30 overflow-hidden rounded-[var(--radius-sm)] bg-[var(--surface-card)] py-1 shadow-[var(--shadow-card)] ring-1 ring-[var(--line-hairline-10)]"
        >
          {items.map((s, i) => (
            <li key={s.id} role="none">
              {/* A div, not a button. The WAI-ARIA combobox pattern keeps DOM
                  focus on the input and points at the current option with
                  `aria-activedescendant`; a focusable option contradicts that,
                  and a focused <button> is activated by `click`, never by the
                  `mousedown` this needs to beat the input's blur. So: not
                  focusable, and both handlers. */}
              <div
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => {
                  e.preventDefault();
                  choose(s);
                }}
                onClick={() => choose(s)}
                onMouseEnter={() => setActive(i)}
                className={`flex w-full cursor-pointer items-center gap-2 px-4 py-2.5 text-left text-[14px] ${
                  i === active
                    ? "bg-[var(--line-hairline-10)] text-[var(--text-primary)]"
                    : "text-[var(--text-primary)]"
                }`}
              >
                <MagnifyingGlass size={15} className="shrink-0 text-[var(--text-muted)]" />
                <span className="min-w-0 flex-1 truncate">
                  {s.canonical_name ?? "Unnamed product"}
                </span>
                {s.category ? (
                  <span className="shrink-0 text-[12px] capitalize text-[var(--text-muted)]">
                    {s.category.replace(/-/g, " ")}
                  </span>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export default SearchAutocomplete;
