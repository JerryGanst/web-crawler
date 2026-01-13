/**
 * 数据洞察悬浮球组件
 *
 * 悬浮在页面右下角的 AI 对话入口
 */

import React, { useState, useEffect } from 'react';
import { MessageCircle, X, Sparkles } from 'lucide-react';
import ChatWindow from './ChatWindow';
import './ChatBall.css';

const ChatBall = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [hasNewMessage, setHasNewMessage] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);

  // 定期闪烁提示
  useEffect(() => {
    if (!isOpen) {
      const interval = setInterval(() => {
        setIsAnimating(true);
        setTimeout(() => setIsAnimating(false), 1000);
      }, 30000); // 每30秒闪烁一次

      return () => clearInterval(interval);
    }
  }, [isOpen]);

  const toggleChat = () => {
    setIsOpen(!isOpen);
    setHasNewMessage(false);
  };

  return (
    <>
      {/* 悬浮球 */}
      <div
        className={`chat-ball ${isAnimating ? 'pulse' : ''} ${hasNewMessage ? 'has-message' : ''}`}
        onClick={toggleChat}
        title="数据洞察助手"
      >
        {isOpen ? (
          <X size={24} className="chat-ball-icon" />
        ) : (
          <>
            <Sparkles size={24} className="chat-ball-icon sparkle" />
            <span className="chat-ball-label">AI</span>
          </>
        )}

        {/* 新消息提示点 */}
        {hasNewMessage && !isOpen && (
          <span className="notification-dot" />
        )}
      </div>

      {/* 聊天窗口 */}
      {isOpen && (
        <ChatWindow
          onClose={() => setIsOpen(false)}
          onNewMessage={() => setHasNewMessage(true)}
        />
      )}
    </>
  );
};

export default ChatBall;
