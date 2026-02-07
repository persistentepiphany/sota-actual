"use client";

import React, { useEffect, useRef, useState } from 'react';

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant' | 'system';
  text: string;
  timestamp?: string;
  isTranscribed?: boolean;
};

interface ChatTimelineProps {
  messages: ChatMessage[];
}

export const ChatTimeline: React.FC<ChatTimelineProps> = ({ messages }) => {
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const timersRef = useRef<Record<string, number>>({});
  const startedRef = useRef<Set<string>>(new Set());
  const [renderedTexts, setRenderedTexts] = useState<Record<string, string>>({});

  const setRenderedText = (id: string, text: string) => {
    setRenderedTexts((prev) => ({ ...prev, [id]: text }));
  };

  // Auto-scroll on new messages AND during typewriter animation
  useEffect(() => {
    if (!bottomRef.current) return;
    bottomRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [messages, renderedTexts]);

  useEffect(() => {
    messages.forEach((msg) => {
      if (startedRef.current.has(msg.id)) return;
      startedRef.current.add(msg.id);

      const role = (msg.role || '').toLowerCase();
      const isAgent = role === 'agent' || role === 'assistant';

      if (!isAgent) {
        setRenderedText(msg.id, msg.text);
        return;
      }

      // Typewriter for assistant
      setRenderedText(msg.id, '');
      let idx = 0;
      const intervalId = window.setInterval(() => {
        idx += 1;
        const next = msg.text.slice(0, idx);
        setRenderedText(msg.id, next);
        if (idx >= msg.text.length) {
          window.clearInterval(intervalId);
          delete timersRef.current[msg.id];
        }
      }, 18);
      timersRef.current[msg.id] = intervalId;
    });
  }, [messages]);

  useEffect(() => {
    return () => {
      Object.values(timersRef.current).forEach((id) => window.clearInterval(id));
      timersRef.current = {};
    };
  }, []);

  if (!messages.length) return null;

  const formatTime = (ts?: string) => {
    if (!ts) return '';
    try {
      return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <div ref={containerRef} className="chat-timeline">
      {messages.map((msg, idx) => {
        const role = (msg.role || '').toLowerCase();
        const isAgent = role === 'agent' || role === 'assistant';
        const isUser = !isAgent;
        const rowClass = isUser ? 'chat-row-user' : 'chat-row-assistant';
        const bubbleClass = [
          isUser ? 'chat-bubble-user' : 'chat-bubble-assistant',
          msg.isTranscribed ? 'chat-bubble-transcribed' : null,
        ]
          .filter(Boolean)
          .join(' ');
        const displayText = renderedTexts[msg.id] ?? (isAgent ? '' : msg.text);
        const isTyping = isAgent && renderedTexts[msg.id] !== undefined && renderedTexts[msg.id].length < msg.text.length;
        const time = formatTime(msg.timestamp);

        return (
          <div
            key={msg.id}
            className={`chat-row ${rowClass}`}
            style={{
              animation: `chatSlideIn 0.3s ease-out both`,
              animationDelay: `${Math.min(idx * 40, 200)}ms`,
            }}
          >
            <div className={`chat-bubble ${bubbleClass}`}>
              <p className="chat-text">
                {displayText}
                {isTyping && <span className="typing-cursor" />}
              </p>
              {time && <span className="chat-time">{time}</span>}
            </div>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
};
