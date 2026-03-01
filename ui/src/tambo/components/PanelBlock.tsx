import { ComponentRenderer } from "@tambo-ai/react";
import { z } from "zod";

import type { UIBlock } from "../../types";
import { toComponentBlock } from "../toComponentBlock";

export const PanelPropsSchema = z.object({
  title: z.string().optional(),
  blocks: z.array(z.any()),
});

export type PanelProps = {
  title?: string;
  blocks: UIBlock[];
};

export function PanelBlock(props: PanelProps) {
  return (
    <div>
      {props.title ? <div className="tm-block-title">{props.title}</div> : null}
      <div style={{ display: "grid", gap: 10 }}>
        {props.blocks.map((block, idx) => (
          <div key={idx} className="tm-block">
            <ComponentRenderer block={toComponentBlock(block) as any} />
          </div>
        ))}
      </div>
    </div>
  );
}
