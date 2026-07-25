import type { ReactNode } from "react";

/**
 * A content block for a long-form page. Copy lives in plain JS strings (not JSX
 * text) so apostrophes and quotes never trip `react/no-unescaped-entities`, and
 * every editorial page renders from the same small vocabulary. `node` is the
 * escape hatch for anything with inline links or buttons.
 */
export type Block =
  | { type: "lead"; text: string }
  | { type: "p"; text: string }
  | { type: "h2"; text: string }
  | { type: "h3"; text: string }
  | { type: "ul"; items: string[] }
  | { type: "ol"; items: string[] }
  | { type: "hr" }
  | { type: "node"; node: ReactNode };

export function Article({
  title,
  meta,
  blocks,
  children,
}: {
  title: string;
  meta?: string;
  blocks: Block[];
  children?: ReactNode;
}) {
  return (
    <div className="prose animate-fade-up">
      <h1>{title}</h1>
      {meta ? <p className="text-[13px] text-[var(--text-muted)]">{meta}</p> : null}
      {blocks.map((block, i) => (
        <BlockView key={i} block={block} />
      ))}
      {children}
    </div>
  );
}

function BlockView({ block }: { block: Block }) {
  switch (block.type) {
    case "lead":
      return <p className="lead">{block.text}</p>;
    case "p":
      return <p>{block.text}</p>;
    case "h2":
      return <h2>{block.text}</h2>;
    case "h3":
      return <h3>{block.text}</h3>;
    case "ul":
      return (
        <ul>
          {block.items.map((it, j) => (
            <li key={j}>{it}</li>
          ))}
        </ul>
      );
    case "ol":
      return (
        <ol>
          {block.items.map((it, j) => (
            <li key={j}>{it}</li>
          ))}
        </ol>
      );
    case "hr":
      return <hr />;
    case "node":
      return <>{block.node}</>;
  }
}

export default Article;
