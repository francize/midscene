/// <reference types="chrome" />

import type { WebUIContext } from '@midscene/web/utils';
import {
  type WorkerRequestGetContext,
  type WorkerRequestSaveContext,
  workerMessageTypes,
} from '../utils';

// 使用全局控制台，因为 console-browserify 在 worker 环境中不能正常工作
const console = globalThis.console;

/**
 * 设置扩展侧面板行为
 * 配置点击扩展图标时打开侧面板，这是 Chrome 扩展 UI 的一部分
 */
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error(error));

/**
 * UI 上下文数据缓存系统
 * 用于在侧面板和全屏 Playground 之间共享上下文数据
 */

/**
 * 生成随机 UUID 作为缓存键
 * @returns 生成的随机字符串
 */
const randomUUID = () => {
  return Math.random().toString(36).substring(2, 15);
};

// 创建缓存映射，用于存储 UI 上下文数据
const cacheMap = new Map<string, WebUIContext>();

/**
 * 设置消息监听器，处理扩展内部的消息通信
 * 处理两种主要消息类型：
 * 1. SAVE_CONTEXT - 保存 UI 上下文并返回 ID
 * 2. GET_CONTEXT - 通过 ID 获取之前保存的上下文
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('Message received in service worker:', request);

  switch (request.type) {
    case workerMessageTypes.SAVE_CONTEXT: {
      // 保存上下文数据并返回唯一 ID
      const payload: WorkerRequestSaveContext = request.payload;
      const { context } = payload;
      const id = randomUUID();
      cacheMap.set(id, context);
      sendResponse({ id });
      break;
    }
    case workerMessageTypes.GET_CONTEXT: {
      // 通过 ID 检索上下文数据
      const payload: WorkerRequestGetContext = request.payload;
      const { id } = payload;
      const context = cacheMap.get(id) as WebUIContext;
      if (!context) {
        sendResponse({ error: 'Screenshot not found' });
      } else {
        sendResponse({ context });
      }

      break;
    }
    default:
      console.log('sending response');
      sendResponse({ error: 'Unknown message type' });
      break;
  }
});
