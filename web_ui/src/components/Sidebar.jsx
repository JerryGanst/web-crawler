import React from 'react';
import { NavLink } from 'react-router-dom';
import { MessageSquare, BookOpen, Bot, BarChart3, Infinity } from 'lucide-react';
import './Sidebar.css';

const Sidebar = () => {
    return (
        <nav className="sidebar">
            <div className="logo-container">
                <div className="logo-bg">
                    <Infinity color="white" size={28} strokeWidth={2.5} />
                </div>
            </div>

            <div className="menu-items">
                <NavLink to="/chat" className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}>
                    <div className="icon-box">
                        <MessageSquare size={24} strokeWidth={1.5} />
                    </div>
                    <span className="label">对话</span>
                </NavLink>

                <NavLink to="/knowledge" className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}>
                    <div className="icon-box">
                        <BookOpen size={24} strokeWidth={1.5} />
                    </div>
                    <span className="label">知识库</span>
                </NavLink>

                <NavLink to="/" className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}>
                    <div className="icon-box">
                        <Bot size={24} strokeWidth={1.5} />
                    </div>
                    <span className="label">工作助手</span>
                </NavLink>

                {/* Added for Project Requirements */}
                <NavLink to="/dashboard" className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}>
                    <div className="icon-box">
                        <BarChart3 size={24} strokeWidth={1.5} />
                    </div>
                    <span className="label">数据看板</span>
                </NavLink>


            </div>
        </nav>
    );
};

export default Sidebar;
