import React, { Suspense, lazy } from 'react';
import { HashRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';

// 路由级代码分割：按需加载页面组件
// 首屏只加载 Sidebar，页面组件延迟加载
const Dashboard = lazy(() => import('./pages/Dashboard_Optimized').then(module => ({ default: module.default })));
const TrendRadar = lazy(() => import('./pages/TrendRadar').then(module => ({ default: module.default })));
const ReportViewer = lazy(() => import('./pages/ReportViewer').then(module => ({ default: module.default })));

// 加载中组件
const PageLoading = () => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    fontSize: '16px',
    color: '#6b7280',
    background: '#f8fafc'
  }}>
    <div style={{ textAlign: 'center' }}>
      <div style={{
        width: '40px',
        height: '40px',
        border: '3px solid #e5e7eb',
        borderTop: '3px solid #3b82f6',
        borderRadius: '50%',
        animation: 'spin 1s linear infinite',
        margin: '0 auto 16px'
      }} />
      <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
      加载中...
    </div>
  </div>
);

function App() {
  return (
    <Router>
      <Suspense fallback={<PageLoading />}>
        <Routes>
          {/* 报告查看页面（无侧边栏） */}
          <Route path="/report/:filename" element={<ReportViewer />} />

          {/* 主布局（有侧边栏） */}
          <Route path="/*" element={
            <div className="app-container">
              <Sidebar />
              <main>
                <Suspense fallback={<PageLoading />}>
                  <Routes>
                    <Route path="/" element={<Navigate to="/radar" replace />} />
                    <Route path="/radar" element={<TrendRadar />} />
                    <Route path="/dashboard" element={<Dashboard />} />
                    {/* <Route path="/chat" element={<div style={{ padding: '40px' }}><h1>AI 对话</h1><p style={{ color: '#64748b' }}>功能开发中...</p></div>} /> */}
                    {/* <Route path="/knowledge" element={<div style={{ padding: '40px' }}><h1>知识广场</h1><p style={{ color: '#64748b' }}>功能开发中...</p></div>} /> */}
                  </Routes>
                </Suspense>
              </main>
            </div>
          } />
        </Routes>
      </Suspense>
    </Router>
  );
}

export default App;
