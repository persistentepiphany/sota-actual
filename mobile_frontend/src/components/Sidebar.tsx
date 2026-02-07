"use client";

import React from 'react';

export interface ConversationSummary {
  id: string;
  title: string | null;
}

interface SidebarProps {
  open: boolean;
  conversations: ConversationSummary[];
  onSelect: (id: string) => void;
  onClose: () => void;
  onNewChat?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  open,
  conversations,
  onSelect,
  onClose,
  onNewChat,
}) => {
  return (
    <div className={`sidebar-backdrop ${open ? 'sidebar-open' : ''}`} onClick={onClose}>
      <div className="sidebar" onClick={(e) => e.stopPropagation()}>
        <div className="sidebar-header">
          <div className="sidebar-header-left">
            <span className="sidebar-title">Conversations</span>
          </div>
          <div className="flex items-center gap-2">
            {onNewChat && (
              <button
                type="button"
                className="icon-button icon-button-small"
                aria-label="New chat"
                onClick={onNewChat}
                title="New conversation"
              >
                +
              </button>
            )}
            <button
              type="button"
              className="icon-button icon-button-small"
              aria-label="Close menu"
              onClick={onClose}
            >
              ✕
            </button>
          </div>
        </div>
        <div className="sidebar-list">
          {conversations.length === 0 && (
            <div className="sidebar-empty">No conversations yet</div>
          )}
          {conversations.map((c) => (
            <button
              key={c.id}
              className="sidebar-item"
              type="button"
              onClick={() => onSelect(c.id)}
            >
              <span className="sidebar-item-title">{c.title || 'Untitled chat'}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
