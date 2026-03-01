export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  role: ChatRole;
  content: string;
};

export type UIBlockText = {
  type: "text";
  title?: string;
  text: string;
};

export type UIBlockJson = {
  type: "json";
  title?: string;
  data: unknown;
};

export type UIBlockComponent = {
  type: "component";
  title?: string;
  component: "Text" | "Json" | "Panel" | "Chart" | "Form";
  props: unknown;
};

export type UIBlock = UIBlockText | UIBlockJson | UIBlockComponent | Record<string, unknown>;

export type StepResult = {
  status: string;
  summary: string;
  artifacts: unknown[];
  metrics: Record<string, unknown>;
  next_actions: string[];
  failure_signature: unknown;
  ui_blocks?: UIBlock[];
};

export type SendResponse = {
  ok: boolean;
  status?: string;
  reply?: string;
  summary?: string;
  artifacts?: unknown[];
  metrics?: Record<string, unknown>;
  next_actions?: string[];
  failure_signature?: unknown;
  ui_blocks?: UIBlock[];
  run_id?: string;
  step_id?: string;
  step_result?: StepResult;
  error?: string;
};
