import path from 'node:path';
import { defineConfig } from '@rsbuild/core';
import { pluginLess } from '@rsbuild/plugin-less';
import { pluginNodePolyfill } from '@rsbuild/plugin-node-polyfill';
import { pluginReact } from '@rsbuild/plugin-react';
import { version } from '../../packages/visualizer/package.json';

/**
 * Rsbuild 构建配置
 * 为 Chrome 扩展定义多环境（web 和 node）构建规则
 */
export default defineConfig({
  /**
   * 环境配置
   * 定义不同环境下的构建规则
   */
  environments: {
    /**
     * Web 环境配置
     * 用于构建扩展的 Web 部分，如弹出窗口和 UI
     */
    web: {
      source: {
        entry: {
          // 主入口文件
          index: './src/index.tsx',
          // 扩展弹出窗口入口
          popup: './src/extension/popup.tsx',
        },
      },
      output: {
        target: 'web',
        sourceMap: true,
      },
    },
    /**
     * Node 环境配置
     * 用于构建在浏览器中运行的脚本，如 Service Worker 和内容脚本
     */
    node: {
      source: {
        entry: {
          // Service Worker 入口
          worker: './src/scripts/worker.ts',
          // 停止水流动画脚本
          'stop-water-flow': './src/scripts/stop-water-flow.ts',
          // 水流动画脚本
          'water-flow': './src/scripts/water-flow.ts',
        },
      },
      output: {
        target: 'node',
        sourceMap: true,
        filename: {
          // 输出到 scripts 目录
          js: 'scripts/[name].js',
        },
      },
    },
  },
  /**
   * 开发模式配置
   * 确保文件写入磁盘，便于 Chrome 扩展调试
   */
  dev: {
    writeToDisk: true,
  },
  /**
   * 输出配置
   */
  output: {
    // 入口处引入 polyfill
    polyfill: 'entry',
    // 注入样式
    injectStyles: true,
    // 复制文件配置
    copy: [
      // 复制静态文件夹
      { from: './static', to: './' },
      // 复制 web-integration 脚本到 scripts 目录
      {
        from: path.resolve(
          __dirname,
          '../../packages/web-integration/iife-script',
        ),
        to: 'scripts',
      },
    ],
  },
  /**
   * 源码配置
   */
  source: {
    define: {
      // 定义 SDK 版本，在代码中可通过 __SDK_VERSION__ 访问
      __SDK_VERSION__: JSON.stringify(version),
    },
  },
  /**
   * 解析配置
   * 处理模块导入和别名
   */
  resolve: {
    alias: {
      // Node.js 模块 polyfill
      async_hooks: path.join(__dirname, './src/scripts/blank_polyfill.ts'),
      'node:async_hooks': path.join(
        __dirname,
        './src/scripts/blank_polyfill.ts',
      ),
      // 确保使用本地 React 模块，避免多实例问题
      react: path.resolve(__dirname, 'node_modules/react'),
      'react-dom': path.resolve(__dirname, 'node_modules/react-dom'),
    },
  },
  /**
   * 插件配置
   * 启用 React、Node polyfill 和 Less 支持
   */
  plugins: [pluginReact(), pluginNodePolyfill(), pluginLess()],
});
