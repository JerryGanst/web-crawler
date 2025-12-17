# 🔧 TrendRadar 前端性能优化报告

## 执行时间
2024年 (当前会话)

## 发现的问题

### 🔴 严重问题：API 重复调用

| API 端点 | 优化前调用次数 | 优化后预期 | 根本原因 |
|---------|--------------|-----------|---------|
| `/api/data` | 16 次 | 1 次 | StrictMode + 轮询无防护 |
| `/api/news/finance` | 6 次 | 1-2 次 | 多组件重复请求 |
| `/api/categories` | 4 次 | 1 次 | StrictMode 双渲染 |
| `/api/commodity-news` | 4 次 | 1 次 | StrictMode 双渲染 |
| `/api/news/supply-chain` | 2 次 | 1 次 | StrictMode 双渲染 |

**总计：33 次 API 调用 → 优化后约 5-6 次**

---

## 修改的文件

### 1. `src/services/api.js` - 完全重写 ✅

**新增功能：**
- 请求级缓存（30秒 TTL）
- 请求去重（同时发起的相同请求共享结果）
- 缓存清除 API
- 调试工具（查看缓存状态）

```javascript
// 使用示例
const response = await api.getData();  // 自动缓存30秒
api.clearCache('data');  // 手动清除缓存
api.getCacheStatus();  // 查看缓存状态
```

### 2. `src/pages/Dashboard.jsx` ✅

**修改内容：**
- 添加 `hasFetchedData` ref 防止 StrictMode 双渲染
- 添加 `intervalRef` 管理定时器
- 使用带缓存的 API 方法

### 3. `src/pages/TrendRadar.jsx` ✅

**修改内容：**
- 添加 `hasFetchedCategories` ref 防止双渲染
- 移除冗余的本地缓存（使用 api.js 统一缓存）
- 简化 loadNews 函数

### 4. `src/components/NewsFeed.jsx` ✅

**修改内容：**
- 添加 `hasFetched` ref 防止双渲染
- 使用 `api.getCommodityNews()` 替代直接 fetch

### 5. `src/components/SupplyChainPanel.jsx` ✅

**修改内容：**
- 添加 `hasFetchedNews` 和 `hasFetchedSupplyNews` ref
- 防止财经新闻和供应链新闻的重复请求

---

## 优化原理

### React StrictMode 问题

```jsx
// main.jsx
<StrictMode>
  <App />
</StrictMode>
```

在开发模式下，StrictMode 会故意将组件渲染两次来帮助发现副作用问题。这导致：
- 每个 `useEffect` 执行两次
- 每个 API 请求发起两次

**解决方案：使用 ref 标记是否已请求**

```jsx
const hasFetched = useRef(false);

useEffect(() => {
  if (hasFetched.current) return;
  hasFetched.current = true;
  
  fetchData();
}, []);
```

### 请求去重

当多个组件同时请求相同数据时，使用 `pendingRequests` Map 确保只发起一次请求：

```javascript
if (pendingRequests.has(key)) {
  return pendingRequests.get(key);  // 返回进行中的 Promise
}
```

---

## 验证方式

1. 刷新页面后打开 Chrome DevTools → Network 标签
2. 观察 API 请求数量，应该从 33 次降低到约 5-6 次
3. 打开 Console，应该能看到缓存命中日志：
   - `[Cache HIT] api:data`
   - `[Cache MISS] api:categories`
   - `[Request DEDUP] api:data - waiting for pending request`

---

## 后续优化建议

### P1 - 后端 API 优化

当前 API 响应时间：
- `/api/news/supply-chain`: **15.8 秒** ⚠️
- `/api/news/finance`: **15.8 秒** ⚠️

建议：
1. 添加后端缓存（Redis）
2. 优化数据库查询
3. 实现分页加载

### P2 - 进一步前端优化

1. **使用 React Query 替代手动缓存**
   ```bash
   npm install @tanstack/react-query
   ```

2. **添加 Loading 骨架屏**

3. **实现虚拟滚动**（针对长列表）

4. **考虑移除 StrictMode**（生产环境自动移除）

---

## 内存优化

当前内存使用：**157.74 MB** (偏高)

建议监控点：
- 组件卸载时清理定时器和事件监听器
- 避免在 state 中存储大量数据
- 使用 React DevTools Profiler 检查重渲染
