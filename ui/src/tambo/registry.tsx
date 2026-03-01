import { z } from "zod";
import type { ComponentType } from "react";

import { ChartBlock, ChartPropsSchema } from "./components/ChartBlock";
import { FormBlock, FormPropsSchema } from "./components/FormBlock";
import { JsonBlock, JsonPropsSchema } from "./components/JsonBlock";
import { PanelBlock, PanelPropsSchema } from "./components/PanelBlock";
import { TextBlock, TextPropsSchema } from "./components/TextBlock";

type RegistryEntry = {
  component: ComponentType<any>;
  propsSchema: z.ZodTypeAny;
};

export const tamboRegistry: Record<string, RegistryEntry> = {
  Text: { component: TextBlock, propsSchema: TextPropsSchema },
  Json: { component: JsonBlock, propsSchema: JsonPropsSchema },
  Panel: { component: PanelBlock, propsSchema: PanelPropsSchema },
  Chart: { component: ChartBlock, propsSchema: ChartPropsSchema },
  Form: { component: FormBlock, propsSchema: FormPropsSchema },
};
