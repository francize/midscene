import type { UIContext } from '@midscene/core';
import { overrideAIConfig } from '@midscene/shared/env';
import {
  ContextPreview,
  type PlaygroundResult,
  PlaygroundResultView,
  PromptInput,
  type ReplayScriptsInfo,
  useEnvConfig,
} from '@midscene/visualizer';
import { allScriptsFromDump } from '@midscene/visualizer';
import { Form, message } from 'antd';
import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * PlaygroundProps 接口
 * 定义 Playground 组件的属性
 */
export interface PlaygroundProps {
  /** 获取浏览器代理实例的函数 */
  getAgent: (forceSameTabNavigation?: boolean) => any | null;
  /** 是否显示上下文预览，默认为 true */
  showContextPreview?: boolean;
  /** 是否为干运行模式，默认为 false */
  dryMode?: boolean;
}

// 设计上未实现的错误代码常量
const ERROR_CODE_NOT_IMPLEMENTED_AS_DESIGNED = 'NOT_IMPLEMENTED_AS_DESIGNED';

/**
 * 格式化错误消息
 * 处理特殊错误类型，提供更友好的错误提示
 * 
 * @param e 错误对象
 * @returns 格式化后的错误消息
 */
const formatErrorMessage = (e: any): string => {
  const errorMessage = e?.message || '';
  if (errorMessage.includes('of different extension')) {
    return 'Conflicting extension detected. Please disable the suspicious plugins and refresh the page. Guide: https://midscenejs.com/quick-experience.html#faq';
  }
  if (!errorMessage?.includes(ERROR_CODE_NOT_IMPLEMENTED_AS_DESIGNED)) {
    return errorMessage;
  }
  return 'Unknown error';
};

// 空结果模板，用于初始化结果状态
const blankResult = {
  result: null,
  dump: null,
  reportHTML: null,
  error: null,
};

/**
 * 浏览器扩展 Playground 组件
 * 提供 AI 驱动的浏览器自动化测试界面，允许用户发送各种 AI 命令并查看结果
 * 
 * @param getAgent 获取浏览器代理的函数
 * @param showContextPreview 是否显示上下文预览，默认为 true
 * @param dryMode 是否为干运行模式，默认为 false
 */
export function BrowserExtensionPlayground({
  getAgent,
  showContextPreview = true,
  dryMode = false,
}: PlaygroundProps) {
  // 状态管理
  const [uiContextPreview, setUiContextPreview] = useState<
    UIContext | undefined
  >(undefined);
  const [loading, setLoading] = useState(false);
  const [loadingProgressText, setLoadingProgressText] = useState('');
  const [result, setResult] = useState<PlaygroundResult | null>(null);
  const [verticalMode, setVerticalMode] = useState(false);
  const [replayScriptsInfo, setReplayScriptsInfo] =
    useState<ReplayScriptsInfo | null>(null);
  const [replayCounter, setReplayCounter] = useState(0);

  // 表单和环境配置
  const [form] = Form.useForm();
  const { config, deepThink } = useEnvConfig();
  const forceSameTabNavigation = useEnvConfig(
    (state) => state.forceSameTabNavigation,
  );

  // 引用
  const runResultRef = useRef<HTMLHeadingElement>(null);
  const currentAgentRef = useRef<any>(null);
  const currentRunningIdRef = useRef<number | null>(0);
  const interruptedFlagRef = useRef<Record<number, boolean>>({});

  // 环境配置检查
  const configAlreadySet = Object.keys(config || {}).length >= 1;

  // 根据窗口宽度设置响应式布局
  useEffect(() => {
    const sizeThreshold = 750;
    setVerticalMode(window.innerWidth < sizeThreshold);

    const handleResize = () => {
      setVerticalMode(window.innerWidth < sizeThreshold);
    };
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  // 应用 AI 配置
  useEffect(() => {
    overrideAIConfig(config);
  }, [config]);

  // 初始化上下文预览
  useEffect(() => {
    if (uiContextPreview) return;
    if (!showContextPreview) return;

    getAgent(forceSameTabNavigation)
      ?.getUIContext()
      .then((context: UIContext) => {
        setUiContextPreview(context);
      })
      .catch((e: any) => {
        message.error('Failed to get UI context');
        console.error(e);
      });
  }, [uiContextPreview, showContextPreview, getAgent, forceSameTabNavigation]);

  /**
   * 重置结果状态
   * 清除当前结果、加载状态和重放脚本信息
   */
  const resetResult = () => {
    setResult(null);
    setLoading(false);
    setReplayScriptsInfo(null);
  };

  /**
   * 处理命令运行
   * 执行表单中指定的 AI 命令，收集结果和转储数据
   */
  const handleRun = useCallback(async () => {
    // 获取表单值
    const value = form.getFieldsValue();
    if (!value.prompt) {
      message.error('Prompt is required');
      return;
    }

    const startTime = Date.now();

    setLoading(true);
    setResult(null);
    const result: PlaygroundResult = { ...blankResult };

    const activeAgent = getAgent(forceSameTabNavigation);
    const thisRunningId = Date.now();
    try {
      if (!activeAgent) {
        throw new Error('No agent found');
      }
      currentAgentRef.current = activeAgent;

      currentRunningIdRef.current = thisRunningId;
      interruptedFlagRef.current[thisRunningId] = false;
      activeAgent.resetDump();
      activeAgent.onTaskStartTip = (tip: string) => {
        if (interruptedFlagRef.current[thisRunningId]) {
          return;
        }
        setLoadingProgressText(tip);
      };

      // 根据命令类型执行不同的 AI 操作
      if (value.type === 'aiAction') {
        result.result = await activeAgent?.aiAction(value.prompt);
      } else if (value.type === 'aiQuery') {
        result.result = await activeAgent?.aiQuery(value.prompt);
      } else if (value.type === 'aiAssert') {
        result.result = await activeAgent?.aiAssert(value.prompt, undefined, {
          keepRawResponse: true,
        });
      } else if (value.type === 'aiTap') {
        result.result = await activeAgent?.aiTap(value.prompt, {
          deepThink,
        });
      }
    } catch (e: any) {
      result.error = formatErrorMessage(e);
      console.error(e);
    }

    // 如果操作被中断，不继续处理结果
    if (interruptedFlagRef.current[thisRunningId]) {
      console.log('interrupted, result is', result);
      return;
    }

    try {
      // 处理扩展模式特定数据
      result.dump = activeAgent?.dumpDataString()
        ? JSON.parse(activeAgent.dumpDataString())
        : null;

      result.reportHTML = activeAgent?.reportHTMLString() || null;
    } catch (e) {
      console.error(e);
    }

    try {
      // 销毁代理页面
      console.log('destroy agent.page', activeAgent?.page);
      await activeAgent?.page?.destroy();
      console.log('destroy agent.page done', activeAgent?.page);
    } catch (e) {
      console.error(e);
    }

    // 更新状态和提取重放脚本信息
    currentAgentRef.current = null;
    setResult(result);
    setLoading(false);
    if (result?.dump) {
      const info = allScriptsFromDump(result.dump);
      setReplayScriptsInfo(info);
      setReplayCounter((c) => c + 1);
    } else {
      setReplayScriptsInfo(null);
    }
    console.log(`time taken: ${Date.now() - startTime}ms`);
  }, [form, getAgent, forceSameTabNavigation]);

  /**
   * 停止正在运行的命令
   * 销毁当前代理并重置状态
   */
  const handleStop = async () => {
    const thisRunningId = currentRunningIdRef.current;
    if (thisRunningId) {
      await currentAgentRef.current?.destroy();
      interruptedFlagRef.current[thisRunningId] = true;
      resetResult();
      console.log('destroy agent done');
    }
  };

  // 检查是否可以运行命令
  const runButtonEnabled = !!getAgent && configAlreadySet;

  // 检查是否可以停止操作
  const stoppable = !dryMode && loading;

  // 获取当前选择的命令类型
  const selectedType = Form.useWatch('type', form);

  return (
    <div className="playground-container vertical-mode">
      <Form form={form} onFinish={handleRun} className="command-form">
        <div className="form-content">
          <div>
            {/* 上下文预览组件 */}
            <ContextPreview
              uiContextPreview={uiContextPreview}
              setUiContextPreview={setUiContextPreview}
              showContextPreview={showContextPreview}
            />

            {/* 提示输入组件 */}
            <PromptInput
              runButtonEnabled={runButtonEnabled}
              form={form}
              serviceMode={'In-Browser-Extension'}
              selectedType={selectedType}
              dryMode={dryMode}
              stoppable={stoppable}
              loading={loading}
              onRun={handleRun}
              onStop={handleStop}
            />
          </div>
          {/* 结果显示区域 */}
          <div className="form-part result-container">
            <PlaygroundResultView
              result={result}
              loading={loading}
              serviceMode={'In-Browser-Extension'}
              replayScriptsInfo={replayScriptsInfo}
              replayCounter={replayCounter}
              loadingProgressText={loadingProgressText}
              verticalMode={verticalMode}
            />
            <div ref={runResultRef} />
          </div>
        </div>
      </Form>
    </div>
  );
}
