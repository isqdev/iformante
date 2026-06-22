"use client";

import {useEffect, useRef} from "react";
import {FileText} from "@gravity-ui/icons";
import {Button, ScrollShadow} from "@heroui/react";
import {Bouncy} from "ldrs/react";
import "ldrs/react/Bouncy.css";

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
                  <Bouncy
                    aria-label="Gerando resposta"
                    color="var(--accent)"
                    size="24"
                    speed="1.75"
                  />
                </span>
              ) : null}
              {message.role === "assistant" &&
              !message.isStreaming &&
              message.sources?.length ? (
                <div className="mt-6">
                  <hr className="mb-4 border-default" />
                  <p className="mb-3 font-medium">Fontes:</p>
                  <div className="flex flex-wrap gap-2">
                    {message.sources.map((source) => (
                      <Button
                        key={source.url || source.filename}
                        onPress={() =>
                          window.open(source.url, "_blank", "noopener,noreferrer")
                        }
                        variant="secondary"
                      >
                        <FileText className="h-4 w-4 shrink-0" />
                        <span className="min-w-0 truncate">
                          {source.filename}
                        </span>
                      </Button>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </ScrollShadow>
  );
}
