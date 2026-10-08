"use client";

import { useMemo, useState } from "react";
import { ChevronRight, File, FileCode, Folder, FolderOpen } from "lucide-react";
import { cn } from "@/lib/utils";

type Node = { name: string; path: string; children: Map<string, Node>; file: boolean };

function build(paths: string[]): Node {
  const root: Node = { name: "", path: "", children: new Map(), file: false };
  for (const path of paths) {
    let node = root;
    path.split("/").forEach((part, index, parts) => {
      const current = parts.slice(0, index + 1).join("/");
      let child = node.children.get(part);
      if (!child) {
        child = { name: part, path: current, children: new Map(), file: index === parts.length - 1 };
        node.children.set(part, child);
      }
      node = child;
    });
  }
  return root;
}

function sorted(node: Node): Node[] {
  return [...node.children.values()].sort((a, b) => Number(a.file) - Number(b.file) || a.name.localeCompare(b.name));
}

/** The repository as a folder tree; changed files and the folders that hold them are marked. */
export function CodeTree({ paths, impacted, indexed, selected, onSelect }: {
  paths: string[];
  impacted: Set<string>;
  indexed: Set<string>;
  selected: string | null;
  onSelect: (path: string) => void;
}) {
  const [onlyImpacted, setOnlyImpacted] = useState(false);
  const shown = useMemo(() => (onlyImpacted ? paths.filter((path) => impacted.has(path)) : paths), [paths, impacted, onlyImpacted]);
  const root = useMemo(() => build(shown), [shown]);
  const hot = useMemo(() => {
    const folders = new Set<string>();
    for (const path of impacted) path.split("/").slice(0, -1).forEach((_, index, parts) => folders.add(parts.slice(0, index + 1).join("/")));
    return folders;
  }, [impacted]);
  const [open, setOpen] = useState<Set<string>>(() => new Set(hot));
  const toggle = (path: string) => setOpen((current) => {
    const next = new Set(current);
    if (next.has(path)) next.delete(path); else next.add(path);
    return next;
  });

  function render(node: Node, depth: number) {
    return sorted(node).map((child) => {
      const isOpen = onlyImpacted || open.has(child.path);
      const changed = child.file ? impacted.has(child.path) : hot.has(child.path);
      const pad = { paddingLeft: `${depth * 14 + 8}px` };
      if (child.file) {
        const Icon = indexed.has(child.path) ? FileCode : File;
        return (
          <li key={child.path}>
            <button type="button" onClick={() => onSelect(child.path)} aria-current={selected === child.path ? "true" : undefined} style={pad}
              className={cn("flex w-full items-center gap-1.5 rounded py-1 pr-2 text-left text-dense hover:bg-surface-raised aria-[current=true]:bg-surface-raised",
                changed ? "font-medium text-text" : "text-muted")}>
              <Icon aria-hidden="true" className={cn("size-3.5 shrink-0", changed ? "text-impact-high" : "")} />
              <span className="truncate">{child.name}</span>
              {changed && <span className="ml-auto shrink-0 rounded-full border border-impact-high/50 px-1.5 text-[11px] text-impact-high">changes</span>}
            </button>
          </li>
        );
      }
      const Icon = isOpen ? FolderOpen : Folder;
      return (
        <li key={child.path}>
          <button type="button" onClick={() => toggle(child.path)} aria-expanded={isOpen} style={pad}
            className={cn("flex w-full items-center gap-1.5 rounded py-1 pr-2 text-left text-dense hover:bg-surface-raised", changed ? "text-text" : "text-muted")}>
            <ChevronRight aria-hidden="true" className={cn("size-3.5 shrink-0 transition-transform duration-150", isOpen && "rotate-90")} />
            <Icon aria-hidden="true" className="size-3.5 shrink-0" />
            <span className="truncate">{child.name}</span>
            {changed && <span aria-label="contains changes" className="ml-auto size-1.5 shrink-0 rounded-full bg-impact-high" />}
          </button>
          {isOpen && <ul>{render(child, depth + 1)}</ul>}
        </li>
      );
    });
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-2.5">
        <span className="text-dense font-medium">Codebase explorer</span>
        <label className="flex items-center gap-1.5 text-meta text-muted">
          <input type="checkbox" checked={onlyImpacted} onChange={(event) => setOnlyImpacted(event.target.checked)} className="accent-[var(--chalk)]" />
          Changed only
        </label>
      </div>
      <ul className="min-h-0 flex-1 overflow-auto p-2" aria-label="Repository files">{render(root, 0)}</ul>
      <p className="border-t border-line px-4 py-2 text-meta text-muted">{paths.length} files · {impacted.size} to change</p>
    </div>
  );
}
