import type { UIBlock, UIBlockComponent } from "../types";

type ComponentBlock = UIBlockComponent;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function toComponentBlock(block: UIBlock): ComponentBlock {
  if (!isRecord(block)) {
    return { type: "component", component: "Json", props: { data: block } };
  }

  const type = typeof block.type === "string" ? block.type : "";
  const title = typeof block.title === "string" ? block.title : undefined;

  if (type === "component" && typeof block.component === "string") {
    const component = block.component as ComponentBlock["component"];
    return { type: "component", title, component, props: block.props ?? {} };
  }

  if (type === "text" && typeof block.text === "string") {
    return { type: "component", title, component: "Text", props: { text: block.text } };
  }

  if (type === "json") {
    return { type: "component", title, component: "Json", props: { data: block.data } };
  }

  return { type: "component", title, component: "Json", props: { data: block } };
}
