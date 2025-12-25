---
trigger: always_on
---

一、通用规范
编码：Python 遵循 PEP 8 + 类型注解 + Google 风格 docstring；前端遵循 ESLint/Prettier，Vue 用 Composition API、React 用 Function Component+Hooks。
工程化：Python 用 Poetry/Pipenv 管理依赖，前端用 pnpm/yarn；模块化拆分，Git 提交遵循 Conventional Commits，分支用 Git Flow；支持 Docker 容器化（Python）、Vite/Webpack 构建优化（前端）。
二、Python 后端规则
架构：优先 FastAPI（异步 / 依赖注入）/Django，数据库用 ORM 避免硬编码 SQL，Redis 做缓存防穿透 / 击穿 / 雪崩，Celery 处理异步任务。
性能 & 安全：核心接口响应≤200ms，异步处理 IO 密集型任务；实现 JWT/OAuth2.0 认证，敏感数据加密，RBAC 权限控制，防 XSS/CSRF/SQL 注入。
测试 & 监控：单元测试覆盖率≥80%（pytest），集成 / 接口自动化测试；集成 Prometheus+Grafana 监控，结构化日志输出。
三、前端规则
架构：Monorepo 管理多包项目，状态管理用 Pinia（Vue）/Redux Toolkit/Zustand（React），路由懒加载 + 权限控制。
性能 & 体验：首屏加载≤3s，图片懒加载 / 骨架屏 / CDN；React 用 useMemo/useCallback、Vue 用 v-memo 减少重渲染；Axios 封装请求，支持拦截 / 重试 / 取消重复请求；适配主流浏览器 + 移动端，友好的交互 / 错误提示。
安全 & 测试：防 XSS/CSRF，单元测试覆盖率≥70%（Jest），E2E 测试（Cypress/Playwright）。
四、交付 & 异常
交付：输出接口文档（Swagger/OpenAPI）、组件文档（Storybook）、部署脚本；代码评审聚焦架构 / 性能 / 安全 / 测试，无未处理异常。
异常：后端全局捕获异常，分类处理并记录日志；前端全局捕获异常，接口异常降级处理，关键功能兜底。
五、扩展要求
技术选型优先成熟活跃的栈，代码遵循开闭原则；后端支持链路追踪，前端集成埋点，保障可观测性。
mysql、redis、mongodb的配置分别在config/database.yaml、config/redis.yaml、config/mongodb.yaml中

测试验证产生的文件，验证完成之后就自动删除