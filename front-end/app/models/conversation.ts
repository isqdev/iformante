import type {Message} from "./message";

export type Conversation = {
  id: string;
  title: string;
  messages: Message[];
};
