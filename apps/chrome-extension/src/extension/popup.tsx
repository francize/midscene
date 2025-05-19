/// <reference types="chrome" />
import { ApiOutlined, HomeOutlined, SendOutlined } from '@ant-design/icons';
import {
  EnvConfig,
  GithubStar,
  Logo,
  globalThemeConfig,
  useEnvConfig,
} from '@midscene/visualizer';
import '@midscene/visualizer/index.css';
import { ConfigProvider, Tabs } from 'antd';
import { BrowserExtensionPlayground } from '../component/playground';
import { getExtensionVersion } from '../utils';
import Bridge from './bridge';
import './popup.less';
import {
  ChromeExtensionProxyPage,
  ChromeExtensionProxyPageAgent,
} from '@midscene/web/chrome-extension';

/**
 * 创建一个用于扩展中特定标签页的代理代理代理
 * 这个函数会创建一个新的代理页面和对应的代理代理代理，用于与浏览器进行交互
 * 注意：需要在标签页被销毁时调用 agent.page.destroy() 销毁代理代理代理以避免内存泄漏
 * 
 * @param forceSameTabNavigation 是否强制在同一个标签页进行导航，默认为 true
 * @returns 返回一个 ChromeExtensionProxyPageAgent 实例
 */
const extensionAgentForTab = (forceSameTabNavigation = true) => {
  const page = new ChromeExtensionProxyPage(forceSameTabNavigation);
  return new ChromeExtensionProxyPageAgent(page);
};

// SDK 版本声明，会在构建时被替换为实际版本号
declare const __SDK_VERSION__: string;

/**
 * PlaygroundPopup 组件
 * Chrome 扩展的主弹出界面，包含 Playground 和 Bridge 两个标签页
 * - Playground：提供浏览器自动化命令测试界面
 * - Bridge 模式：允许从本地终端通过 Midscene SDK 控制浏览器
 */
export function PlaygroundPopup() {
  // 获取扩展版本号
  const extensionVersion = getExtensionVersion();
  // 从环境配置中获取当前活动的标签页和设置函数
  const { popupTab, setPopupTab } = useEnvConfig();

  // 定义标签页配置
  const items = [
    {
      key: 'playground',
      label: 'Playground',
      icon: <SendOutlined />,
      children: (
        <div className="popup-playground-container">
          <BrowserExtensionPlayground
            getAgent={(forceSameTabNavigation?: boolean) => {
              return extensionAgentForTab(forceSameTabNavigation);
            }}
            showContextPreview={false}
          />
        </div>
      ),
    },
    {
      key: 'bridge',
      label: 'Bridge Mode',
      children: (
        <div className="popup-bridge-container">
          <Bridge />
        </div>
      ),
      icon: <ApiOutlined />,
    },
  ];

  return (
    <ConfigProvider theme={globalThemeConfig()}>
      <div className="popup-wrapper">
        <div className="popup-header">
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '10px',
            }}
          >
            {/* 主页链接图标 */}
            <a
              style={{
                color: 'unset',
              }}
              href="https://midscenejs.com/"
              target="_blank"
              rel="noreferrer"
            >
              <HomeOutlined
                style={{
                  fontSize: '20px',
                  cursor: 'pointer',
                  textDecoration: 'none',
                }}
              />
            </a>
            {/* GitHub Star 组件 */}
            <GithubStar />
            {/* 环境配置组件，仅在 playground 标签页显示提示 */}
            <EnvConfig showTooltipWhenEmpty={popupTab === 'playground'} />
          </div>
          <p>
            AI-Driven Browser Automation with Chrome Extensions, JavaScript, and
            YAML Scripts.{' '}
            <a href="https://midscenejs.com/" target="_blank" rel="noreferrer">
              Learn more
            </a>
          </p>
        </div>
        {/* 标签页容器 */}
        <div className="tabs-container">
          <Tabs
            defaultActiveKey="playground"
            activeKey={popupTab}
            items={items}
            onChange={(key) => setPopupTab(key as 'playground' | 'bridge')}
          />
        </div>

        {/* 底部版本信息 */}
        <div className="popup-footer">
          <p>
            Midscene.js Chrome Extension v{extensionVersion} (SDK v
            {__SDK_VERSION__})
          </p>
        </div>
      </div>
    </ConfigProvider>
  );
}
