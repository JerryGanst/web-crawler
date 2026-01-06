import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === 'serve' ? '/' : './',
  
  build: {
    // 代码分割配置
    rollupOptions: {
      output: {
        // 手动分包策略
        manualChunks: (id) => {
          // React 核心库单独打包
          if (id.includes('node_modules/react/') || 
              id.includes('node_modules/react-dom/')) {
            return 'react-vendor';
          }
          
          // React Router 单独打包
          if (id.includes('node_modules/react-router')) {
            return 'router';
          }
          
          // ECharts 单独打包（按需加载）
          if (id.includes('node_modules/echarts')) {
            return 'echarts';
          }
          
          // Lucide 图标库单独打包
          if (id.includes('node_modules/lucide-react')) {
            return 'icons';
          }
          
          // Axios 和其他网络库
          if (id.includes('node_modules/axios')) {
            return 'http';
          }
          
          // 其他第三方库
          if (id.includes('node_modules')) {
            return 'vendor';
          }
        },
        
        // 分块命名
        chunkFileNames: (chunkInfo) => {
          const facadeModuleId = chunkInfo.facadeModuleId || '';
          if (facadeModuleId.includes('pages/')) {
            return 'pages/[name]-[hash].js';
          }
          return 'chunks/[name]-[hash].js';
        },
        
        // 入口文件命名
        entryFileNames: 'js/[name]-[hash].js',
        
        // 静态资源命名
        assetFileNames: (assetInfo) => {
          const extType = assetInfo.name.split('.').pop();
          if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(extType)) {
            return 'images/[name]-[hash][extname]';
          }
          if (/css/i.test(extType)) {
            return 'css/[name]-[hash][extname]';
          }
          return 'assets/[name]-[hash][extname]';
        }
      }
    },
    
    // 分块大小警告阈值（500KB）
    chunkSizeWarningLimit: 500,
    
    // 使用 esbuild 压缩（内置，无需额外依赖）
    minify: 'esbuild',
    
    // esbuild 压缩选项
    esbuild: {
      drop: command === 'build' ? ['console', 'debugger'] : [],
      legalComments: 'none',
    },
    
    // 生成 sourcemap（便于调试）
    sourcemap: command === 'serve',
    
    // 输出目录
    outDir: 'dist',
    
    // 清空输出目录
    emptyOutDir: true,
  },
  
  // 开发服务器配置
  server: {
    port: 5173,
    open: true,
    cors: true,
    // 代理配置（可选，用于解决跨域）
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  },
  
  // 预览服务器配置
  preview: {
    port: 4173,
  },
  
  // 依赖优化
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      'axios',
    ],
    // 排除不需要预构建的依赖
    exclude: []
  },
  
  // 解析配置
  resolve: {
    alias: {
      '@': '/src',
      '@components': '/src/components',
      '@pages': '/src/pages',
      '@services': '/src/services',
      '@assets': '/src/assets',
    }
  },
  
  // 定义全局常量
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version || '1.0.0'),
  }
}))
