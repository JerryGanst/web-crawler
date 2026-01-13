/**
 * 聊天窗口组件
 *
 * 提供完整的聊天界面，支持：
 * - 多轮对话
 * - 会话历史
 * - Markdown 渲染
 * - 加载状态
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  X,
  Send,
  Trash2,
  RefreshCw,
  Maximize2,
  Minimize2,
  Bot,
  User,
  AlertCircle,
  Loader2
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './ChatWindow.css';

// API 配置
const API_BASE = '/api/chat';

const ChatWindow = ({ onClose, onNewMessage }) => {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [error, setError] = useState(null);
  const [isCrawling, setIsCrawling] = useState(false);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // 滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 初始化：获取或创建会话
  useEffect(() => {
    const storedSessionId = localStorage.getItem('chat_session_id');
    if (storedSessionId) {
      setSessionId(storedSessionId);
      loadHistory(storedSessionId);
    } else {
      createNewSession();
    }
  }, []);

  // 创建新会话
  const createNewSession = async () => {
    try {
      const response = await fetch(`${API_BASE}/new-session`, {
        method: 'POST'
      });
      const data = await response.json();
      if (data.success) {
        setSessionId(data.session_id);
        localStorage.setItem('chat_session_id', data.session_id);
        setMessages([{
          role: 'assistant',
          content: '你好！我是数据洞察助手。我可以帮你查询新闻热搜、分析话题趋势、对比不同时期的热点变化。你想了解什么？',
          timestamp: new Date().toISOString()
        }]);
      }
    } catch (err) {
      console.error('创建会话失败:', err);
      // 使用本地会话ID
      const localId = `local_${Date.now()}`;
      setSessionId(localId);
      localStorage.setItem('chat_session_id', localId);
    }
  };

  // 加载历史记录
  const loadHistory = async (sid) => {
    try {
      const response = await fetch(`${API_BASE}/history/${sid}`);
      const data = await response.json();
      if (data.success && data.messages.length > 0) {
        setMessages(data.messages);
      } else {
        // 没有历史，显示欢迎消息
        setMessages([{
          role: 'assistant',
          content: '你好！我是数据洞察助手。我可以帮你查询新闻热搜、分析话题趋势、对比不同时期的热点变化。你想了解什么？',
          timestamp: new Date().toISOString()
        }]);
      }
    } catch (err) {
      console.error('加载历史失败:', err);
    }
  };

  // 发送消息
  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage = {
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/hybrid`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: userMessage.content,
          session_id: sessionId
        })
      });

      const data = await response.json();

      if (data.success) {
        const assistantMessage = {
          role: 'assistant',
          content: data.message,
          timestamp: data.timestamp
        };
        setMessages(prev => [...prev, assistantMessage]);
        onNewMessage?.();
      } else {
        setError(data.error || '请求失败');
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: `抱歉，处理请求时出现错误：${data.error || '未知错误'}`,
          timestamp: new Date().toISOString(),
          isError: true
        }]);
      }
    } catch (err) {
      console.error('发送消息失败:', err);
      setError(err.message);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '网络连接失败，请检查后端服务是否运行。',
        timestamp: new Date().toISOString(),
        isError: true
      }]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  // 清空对话
  const clearChat = async () => {
    if (!window.confirm('确定要清空对话历史吗？')) return;

    try {
      if (sessionId) {
        await fetch(`${API_BASE}/history/${sessionId}`, {
          method: 'DELETE'
        });
      }
    } catch (err) {
      console.error('清空历史失败:', err);
    }

    // 创建新会话
    localStorage.removeItem('chat_session_id');
    createNewSession();
  };

  // 键盘事件
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // 触发爬虫
  const triggerCrawl = async () => {
    setIsCrawling(true);
    try {
      const response = await fetch(`${API_BASE}/trigger-crawl`, {
        method: 'POST'
      });
      const data = await response.json();
      
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.success 
          ? '🚀 爬虫已启动！正在获取最新热搜数据，请稍等 30-60 秒后再次提问。'
          : `❌ 启动失败：${data.error}`,
        timestamp: new Date().toISOString()
      }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '❌ 网络错误，无法启动爬虫',
        timestamp: new Date().toISOString(),
        isError: true
      }]);
    } finally {
      setIsCrawling(false);
    }
  };

  // 快捷提问
  const quickQuestions = [
    '最近有什么热门新闻？',
    '分析AI话题的趋势',
    '对比本周和上周的热点',
    '知乎上讨论最多的是什么？'
  ];

  return (
    <div className={`chat-window ${isExpanded ? 'expanded' : ''}`}>
      {/* 头部 */}
      <div className="chat-header">
        <div className="chat-header-left">
          <Bot size={20} className="chat-header-icon" />
          <span className="chat-title">数据洞察助手</span>
        </div>
        <div className="chat-header-actions">
          <button
            className="chat-action-btn"
            onClick={clearChat}
            title="清空对话"
          >
            清空
          </button>
          <button
            className="chat-action-btn"
            onClick={() => setIsExpanded(!isExpanded)}
            title={isExpanded ? '缩小' : '放大'}
          >
            {isExpanded ? '缩小' : '放大'}
          </button>
          <button
            className="chat-action-btn close"
            onClick={onClose}
            title="关闭"
          >
            关闭
          </button>
        </div>
      </div>

      {/* 消息列表 */}
      <div className="chat-messages">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`chat-message ${msg.role} ${msg.isError ? 'error' : ''}`}
          >
            <div className="message-avatar">
              {msg.role === 'user' ? (
                <User size={16} />
              ) : (
                <Bot size={16} />
              )}
            </div>
            <div className="message-content">
              {msg.role === 'assistant' ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
              ) : (
                <p>{msg.content}</p>
              )}
              <span className="message-time">
                {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString('zh-CN', {
                  hour: '2-digit',
                  minute: '2-digit'
                }) : ''}
              </span>
            </div>
          </div>
        ))}

        {/* 加载状态 */}
        {isLoading && (
          <div className="chat-message assistant loading">
            <div className="message-avatar">
              <Bot size={16} />
            </div>
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 快捷提问（仅在没有消息或只有欢迎消息时显示） */}
      {messages.length <= 1 && (
        <div className="quick-questions">
          {quickQuestions.map((q, i) => (
            <button
              key={i}
              className="quick-question-btn"
              onClick={() => {
                setInputValue(q);
                inputRef.current?.focus();
              }}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* 输入区域 */}
      <div className="chat-input-area">
        <textarea
          ref={inputRef}
          className="chat-input"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入你的问题..."
          rows={1}
          disabled={isLoading}
        />
        {isLoading ? (
          <button
            className="chat-stop-btn"
            onClick={() => setIsLoading(false)}
            title="终止回复"
          >
            终止
          </button>
        ) : (
          <button
            className="chat-send-btn"
            onClick={sendMessage}
            disabled={!inputValue.trim()}
          >
            发送
          </button>
        )}
      </div>

      {/* 底部提示 */}
      <div className="chat-footer">
        <span>Powered by Gemini 2.5 Pro</span>
        {sessionId && (
          <span className="session-id">会话: {sessionId}</span>
        )}
      </div>
    </div>
  );
};

export default ChatWindow;
