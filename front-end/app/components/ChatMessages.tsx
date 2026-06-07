"use client";

import {useEffect, useRef} from "react";
import {ScrollShadow, Spinner} from "@heroui/react";

import type {Message} from "../models/message";
import {ParseMarkdown} from "./ParseMarkdown";

type ChatMessagesProps = {
  messages: Message[];
};

export function ChatMessages({messages}: ChatMessagesProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const latestUserMessageId = [...messages]
    .reverse()
    .find((message) => message.role === "user")?.id;

  useEffect(() => {
    const scrollContainer = scrollContainerRef.current;
    const latestUserMessage = scrollContainer?.querySelector<HTMLElement>(
      "[data-latest-user-message]",
    );

    if (!scrollContainer || !latestUserMessage) {
      return;
    }

    requestAnimationFrame(() => {
      scrollContainer.scrollTo({
        behavior: "smooth",
        top: Math.max(latestUserMessage.offsetTop - 24, 0),
      });
    });
  }, [latestUserMessageId]);

  return (
    <ScrollShadow ref={scrollContainerRef} className="min-h-0 flex-1">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-4 py-8 md:px-6">
        {messages.map((message) => (
          <article
            key={message.id}
            className={message.role === "user" ? "ml-auto max-w-2xl" : "max-w-2xl"}
            data-latest-user-message={
              message.id === latestUserMessageId ? true : undefined
            }
            data-message-role={message.role}
          >
            <div
              className={"text-base leading-7 " + (message.role === "user" ? "rounded-2xl bg-default px-4 py-3" : "text-foreground")}
            >
              {message.content ? <ParseMarkdown content={message.content} /> : null}
              {message.role === "assistant" && message.isStreaming ? (
                <span
                  className={"flex items-center text-foreground " + (message.content ? "mt-3" : "")}
                >
                  <Spinner
                    aria-label="Gerando resposta"
                    className="chat-response-spinner"
                    color="accent"
                    size="sm"
                  />
                </span>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </ScrollShadow>
  );
}
