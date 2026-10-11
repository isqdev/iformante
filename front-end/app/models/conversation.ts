import type {Message} from "./message";

export type Conversation = {
  channel?: "text" | "speech";
  id: string;
  title: string;
  messages: Message[];
};
