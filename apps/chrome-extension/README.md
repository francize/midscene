# Midscene Chrome DevTools

Chrome extension version of the Midscene tool, providing browser automation, Bridge mode, and a Playground testing environment.

## 功能概述

Midscene Chrome 扩展是一个强大的浏览器自动化工具，为开发者提供了以下核心功能：

1. **Playground 模式**：直接在浏览器中通过 AI 指令测试和执行自动化任务
2. **Bridge 模式**：允许从本地终端通过 Midscene SDK 控制浏览器，实现脚本和手动交互的无缝结合
3. **可视化反馈**：通过水流动画和鼠标指针动画提供直观的自动化过程反馈

这个扩展是 Midscene 项目的浏览器集成部分，旨在简化浏览器自动化开发和测试流程。

## 架构设计

Midscene Chrome 扩展采用模块化架构，主要由以下部分组成：

### 核心组件

1. **Popup UI**：扩展的弹出界面，包含 Playground 和 Bridge 两个主要标签页
2. **Service Worker**：管理扩展生命周期和处理消息通信
3. **内容脚本**：注入到页面的脚本，提供页面交互能力和可视化反馈
4. **中间件**：桥接 Chrome API 和 Midscene SDK 的连接层

### 详细架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                               Chrome 扩展                                     │
│                                                                             │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────────────────┐   │
│  │               │    │               │    │                           │   │
│  │   Popup UI    │    │ Service Worker│    │      Content Scripts      │   │
│  │               │    │               │    │                           │   │
│  │ ┌───────────┐ │    │ ┌───────────┐ │    │ ┌─────────┐  ┌─────────┐  │   │
│  │ │Playground │ │    │ │  消息处理  │ │    │ │水流动画 │  │鼠标指针 │  │   │
│  │ │   界面    │ │    │ │           │ │    │ │        │  │        │  │   │
│  │ └───────────┘ │    │ └───────────┘ │    │ └─────────┘  └─────────┘  │   │
│  │ ┌───────────┐ │    │ ┌───────────┐ │    │ ┌─────────────────────┐   │   │
│  │ │  Bridge   │ │    │ │上下文缓存 │ │    │ │     DOM 操作        │   │   │
│  │ │   界面    │ │    │ │           │ │    │ │                     │   │   │
│  │ └───────────┘ │    │ └───────────┘ │    │ └─────────────────────┘   │   │
│  │               │    │               │    │                           │   │
│  └───────┬───────┘    └───────┬───────┘    └─────────────┬─────────────┘   │
│          │                    │                          │                 │
│          ▼                    ▼                          ▼                 │
│  ┌───────────────────────────────────────────────────────────────────┐     │
│  │                          Chrome API                               │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                │                    │                          │
                │                    │                          │
                ▼                    ▼                          ▼
┌───────────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐
│                       │  │                  │  │                          │
│   Midscene SDK        │  │ 本地终端(Bridge) │  │      目标网页 DOM        │
│                       │  │                  │  │                          │
└───────────────────────┘  └──────────────────┘  └──────────────────────────┘
```

### 组件交互流程

#### Playground 模式流程

```
┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐
│            │     │            │     │            │     │            │     │            │
│  用户输入  │ ──> │ Playground │ ──> │  AI 处理   │ ──> │ 内容脚本   │ ──> │ 浏览器自动化 │
│   命令     │     │  组件处理  │     │            │     │ 执行操作   │     │            │
│            │     │            │     │            │     │            │     │            │
└────────────┘     └────────────┘     └────────────┘     └────────────┘     └────────────┘
                                                            │     ▲
                                                            │     │
                                                            ▼     │
                                                        ┌────────────┐
                                                        │            │
                                                        │ 可视化反馈  │
                                                        │            │
                                                        └────────────┘
```

#### Bridge 模式流程

```
┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐
│            │     │            │     │            │     │            │
│ 扩展中启用  │ ──> │ 本地 SDK   │ ──> │ 建立通信   │ ──> │ 浏览器操作  │
│ Bridge 连接 │     │ 连接请求   │     │ 通道       │     │            │
│            │     │            │     │            │     │            │
└────────────┘     └────────────┘     └────────────┘     └────────────┘
                                          │   ▲
                                          │   │
                                          ▼   │
                                      ┌────────────┐
                                      │            │
                                      │Service Worker│
                                      │ 消息中继    │
                                      │            │
                                      └────────────┘
```

### 数据流

```
+----------------+        +----------------+        +----------------+
|                |        |                |        |                |
|   Popup UI     | <----> | Service Worker | <----> |  网页内容脚本   |
|                |        |                |        |                |
+----------------+        +----------------+        +----------------+
        ^                         ^                         ^
        |                         |                         |
        v                         v                         v
+----------------+        +----------------+        +----------------+
|                |        |                |        |                |
| Midscene SDK   | <----> |  Chrome API    | <----> | 目标网页 DOM   |
|                |        |                |        |                |
+----------------+        +----------------+        +----------------+
```

### 技术栈

- **UI 框架**：React + Ant Design
- **构建工具**：Rsbuild (基于 Webpack)
- **样式处理**：Less
- **数据管理**：Zustand
- **类型系统**：TypeScript

## Development Guide

### Environment Setup

Make sure you have completed the basic environment setup according to the main project's [Contribution Guide](../../CONTRIBUTING.md).

### Directory Structure

```
chrome-extension/
├── dist/                 # 构建输出目录，可以直接安装为 Chrome 扩展
├── extension_output/     # 打包的 Chrome 扩展输出目录
│   └── midscene-extension-v{version}.zip    # 压缩后的扩展包
├── scripts/              # 构建和工具脚本
│   └── pack-extension.js          # 打包 Chrome 扩展的脚本
├── src/                  # 源代码
│   ├── component/        # React 组件
│   │   └── playground.tsx # Playground 组件实现
│   ├── extension/        # Chrome 扩展相关组件
│   │   ├── bridge.tsx    # Bridge 模式 UI 实现
│   │   ├── popup.tsx     # 扩展弹出窗口主页
│   │   ├── misc.tsx      # 辅助组件和图标
│   │   ├── utils.ts      # 实用函数
│   │   ├── common.less   # 通用样式变量
│   │   ├── popup.less    # 弹出窗口样式
│   │   └── bridge.less   # Bridge 模式样式
│   ├── scripts/          # 注入页面的脚本
│   │   ├── blank_polyfill.ts # Node.js 模块的浏览器端 polyfill
│   │   ├── worker.ts     # Service Worker 实现
│   │   ├── stop-water-flow.ts # 停止水流动画的脚本
│   │   └── water-flow.ts # 水流动画实现
│   ├── store.tsx         # 全局状态管理
│   ├── utils.ts          # 通用工具函数
│   ├── index.tsx         # 主入口
│   └── App.tsx           # 主应用组件
├── static/               # 静态资源目录，会被复制到 dist 目录
│   ├── fonts/            # 字体资源
│   ├── icon128.png       # 扩展图标
│   └── manifest.json     # Chrome 扩展清单文件
├── package.json          # 项目配置
├── rsbuild.config.ts     # Rsbuild 构建配置
└── ...
```

### Development Process

1. **安装依赖**
```bash
pnpm install
```

2. **构建依赖包**
```bash
# 在项目根目录构建所有包
pnpm run build
```

3. **开发模式**
```bash
# 以开发模式启动项目
cd apps/chrome-extension
pnpm run dev
```

4. **构建项目**
```bash
# 构建 Chrome 扩展
cd apps/chrome-extension
pnpm run build
```

构建过程包括：
- 使用 rsbuild 构建 Web 应用程序
- 生成报告模板脚本 (report-template.js)
- 将构建产物打包为 Chrome 扩展

### Installing the Extension

#### Method 1: Using the dist directory (for development and debugging)

The built `dist` directory can be directly installed as a Chrome extension:
1. 打开 Chrome 浏览器，导航到 `chrome://extensions/`
2. 在右上角启用"开发者模式"
3. 点击左上角的"加载已解压的扩展程序"
4. 选择 `apps/chrome-extension/dist` 目录

这种方法适合开发过程中的快速测试。

#### Method 2: Using the packaged extension file

For publishing or sharing:
1. 使用 `pnpm run build` 命令构建项目
2. 在 `extension_output` 目录中找到 `midscene-extension-v{version}.zip` 文件
3. 将此文件上传到 Chrome Web Store 开发者控制台，或与他人分享以安装

### Debugging Tips

#### 调试扩展后台

1. 在 Chrome 扩展页面 (`chrome://extensions/`) 找到 Midscene 扩展
2. 点击"Service Worker"链接打开开发者工具
3. 使用控制台和网络面板进行调试

#### 调试弹出窗口

1. 点击 Chrome 工具栏中的 Midscene 图标打开扩展弹出窗口
2. 右键点击弹出窗口并选择"检查"
3. 使用开发者工具调试 UI 和交互

#### 调试内容脚本

1. 打开任意网页，点击 Midscene 图标激活扩展
2. 打开开发者工具
3. 在"源代码"面板下的"内容脚本"部分找到 Midscene 脚本

### Feature Description

#### Playground 模式

Playground 模式允许你直接在浏览器中测试和执行 Midscene 的 AI 驱动自动化命令。支持的命令类型包括：

- **aiAction**: 执行复杂的自动化操作序列
- **aiQuery**: 查询网页内容并返回结果
- **aiAssert**: 验证网页状态或内容
- **aiTap**: 基于自然语言提示点击页面元素

每个命令执行后，结果和执行过程会显示在界面中，包括执行日志和可重放的脚本信息。

#### Bridge 模式

Bridge 模式允许从本地终端通过 Midscene SDK 控制浏览器。这在以下场景非常有用：

1. 同时通过脚本和手动操作控制浏览器
2. 复用浏览器的 cookie 和会话
3. 与本地开发环境集成
4. 在复杂自动化流程中插入手动步骤

Bridge 模式需要先在扩展中启用连接，然后从本地 Midscene SDK 连接到浏览器。

#### 可视化反馈

扩展提供了两种可视化反馈机制：

1. **水流动画**：在页面边缘显示蓝色水流效果，指示自动化过程正在进行
2. **鼠标指针动画**：显示自动化操作的点击和交互位置

这些视觉提示帮助用户理解自动化过程中发生的操作。

## Release Process

1. 更新 `package.json` 中的版本号，使其与主项目匹配
2. 运行构建：`pnpm run build`
3. 验证在 `extension_output` 目录中生成的 `midscene-extension-v{version}.zip` 文件
4. 将 ZIP 文件提交到 Chrome Web Store

## Troubleshooting

### Common Issues

1. **报告模板生成失败**
   - 确保先构建 `@midscene/visualizer` 包
   - 检查 `packages/visualizer/dist/report/index.html` 是否存在

2. **React Hooks 错误**
   - 检查是否存在多个 React 实例，可能需要调整 `rsbuild.config.ts` 中的 externals 配置
   - 确保正确使用了别名配置，避免多个 React 实例

3. **async_hooks module not found**
   - 检查 `rsbuild.config.ts` 中的别名配置是否正确指向 polyfill 文件
   - 确保 blank_polyfill.ts 被正确导入和使用

4. **安装后扩展不能正常工作**
   - 检查 Chrome 控制台中的错误消息
   - 验证构建过程是否完全执行
   - 验证 manifest.json 文件中的权限配置
   - 在开发者工具中查看网络请求是否有 CORS 错误

5. **扩展操作无响应**
   - 检查权限是否正确设置
   - 尝试重新加载扩展和页面
   - 确认目标页面没有阻止内容脚本注入
