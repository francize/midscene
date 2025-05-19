/// <reference types="chrome" />
import type { WebUIContext } from '@midscene/web/utils';

/**
 * 定义与 Service Worker 通信的消息类型常量
 */
export const workerMessageTypes = {
  /** 保存上下文数据的消息类型 */
  SAVE_CONTEXT: 'save-context',
  /** 获取上下文数据的消息类型 */
  GET_CONTEXT: 'get-context',
};

/**
 * 保存上下文数据请求的接口
 * 包含要保存的 WebUIContext 对象
 */
export interface WorkerRequestSaveContext {
  context: WebUIContext;
}

/**
 * 保存上下文数据响应的接口
 * 包含生成的唯一标识符
 */
export interface WorkerResponseSaveContext {
  id: string;
}

/**
 * 获取上下文数据请求的接口
 * 通过 ID 请求之前保存的上下文
 */
export interface WorkerRequestGetContext {
  id: string;
}

/**
 * 获取上下文数据响应的接口
 * 包含请求的 WebUIContext 对象
 */
export interface WorkerResponseGetContext {
  context: WebUIContext;
}

/**
 * 向 Service Worker 发送消息的通用函数
 * 
 * @param type 消息类型
 * @param payload 消息数据
 * @returns Promise，解析为 Worker 响应
 */
export async function sendToWorker<Payload, Result = any>(
  type: string,
  payload: Payload,
): Promise<Result> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type, payload }, (response) => {
      if (response.error) {
        reject(response.error);
      } else {
        resolve(response);
      }
    });
  });
}

/**
 * 获取 Playground 页面 URL
 * 带有缓存上下文 ID 参数的完整 URL
 * 
 * @param cacheContextId 上下文缓存 ID
 * @returns Playground 页面 URL
 */
export function getPlaygroundUrl(cacheContextId: string) {
  return chrome.runtime.getURL(
    `./pages/playground.html?cache_context_id=${cacheContextId}`,
  );
}

/**
 * 获取当前活动标签页
 * 
 * @returns Promise，解析为当前活动的 Chrome 标签页
 */
export async function activeTab(): Promise<chrome.tabs.Tab> {
  return new Promise((resolve, reject) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs?.[0]) {
        resolve(tabs[0]);
      } else {
        reject(new Error('No active tab found'));
      }
    });
  });
}

/**
 * 获取当前窗口 ID
 * 
 * @returns Promise，解析为当前 Chrome 窗口的 ID
 */
export async function currentWindowId(): Promise<number> {
  return new Promise((resolve, reject) => {
    chrome.windows.getCurrent((window) => {
      if (window?.id) {
        resolve(window.id);
      } else {
        reject(new Error('No active window found'));
      }
    });
  });
}

/**
 * 获取扩展版本号
 * 从扩展清单文件中获取版本信息
 * 
 * @returns 扩展版本号或 'unknown'
 */
export function getExtensionVersion() {
  return chrome.runtime?.getManifest()?.version || 'unknown';
}
