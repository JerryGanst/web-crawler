import React from 'react';
import { NavLink } from 'react-router-dom';
import { MessageSquare, Compass, Bot, BarChart3, Radar, TrendingUp } from 'lucide-react';
import './Sidebar.css';

const Sidebar = () => {
    return (
        <nav className="sidebar">
            <div className="logo-container">
                <div className="logo-bg">
                    <Radar color="white" size={28} strokeWidth={2.5} />
                </div>
            </div>

            <div className="menu-items">
                {/* 热点雷达 - 主要功能 */}
                <NavLink to="/radar" className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}>
                    <div className="icon-box">
                        <TrendingUp size={24} strokeWidth={1.5} />
                    </div>
                    <span className="label">热点雷达</span>
                </NavLink>

                {/* 数据看板 */}
                <NavLink to="/dashboard" className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}>
                    <div className="icon-box">
                        <BarChart3 size={24} strokeWidth={1.5} />
                    </div>
                    <span className="label">数据看板</span>
                </NavLink>

                {/* 知识广场 (暂未开放) */}
                {/* <NavLink to="/knowledge" className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}>
                    <div className="icon-box">
                        <Compass size={24} strokeWidth={1.5} />
                    </div>
                    <span className="label">知识广场</span>
                </NavLink> */}

                {/* 对话 (暂未开放) */}
                {/* <NavLink to="/chat" className={({ isActive }) => `menu-item ${isActive ? 'active' : ''}`}>
                    <div className="icon-box">
                        <MessageSquare size={24} strokeWidth={1.5} />
                    </div>
                    <span className="label">AI对话</span>
                </NavLink> */}
            </div>
        </nav>
    );
};

export default Sidebar;
