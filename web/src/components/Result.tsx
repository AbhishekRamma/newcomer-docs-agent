import type { AskResponse } from "../types";
import { Answer } from "./Answer";
import { RefusalPanel } from "./RefusalPanel";

export function Result({ data }: { data: AskResponse }) {
  return data.refused ? <RefusalPanel data={data} /> : <Answer data={data} />;
}
