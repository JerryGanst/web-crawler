import React from 'react';
import { HashRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import TrendRadar from './pages/TrendRadar';
import ReportViewer from './pages/ReportViewer';

function App() {
  return (
    <Router>
      <Routes>
        {/* 报告查看页面（无侧边栏） */}
        <Route path="/report/:filename" element={<ReportViewer />} />
        
        {/* 主布局（有侧边栏） */}
        <Route path="/*" element={
          <div className="app-container">
            <Sidebar />
            <main>
              <Routes>
                <Route path="/" element={<Navigate to="/radar" replace />} />
                <Route path="/radar" element={<TrendRadar />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/chat" element={<div style={{padding: '40px'}}><h1>AI 对话</h1><p style={{color: '#64748b'}}>功能开发中...</p></div>} />
                <Route path="/knowledge" element={<div style={{padding: '40px'}}><h1>知识广场</h1><p style={{color: '#64748b'}}>功能开发中...</p></div>} />
              </Routes>
            </main>
          </div>
        } />
      </Routes>
    </Router>
  );
}

export default App;
