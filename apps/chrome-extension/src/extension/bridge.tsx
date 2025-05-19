import { LoadingOutlined } from '@ant-design/icons';
import { ExtensionBridgePageBrowserSide } from '@midscene/web/bridge-mode-browser';
import { Button, Spin } from 'antd';
import dayjs from 'dayjs';
import { useEffect, useRef, useState } from 'react';
import './bridge.less';
import { iconForStatus } from './misc';

/**
 * Bridge 日志项接口
 * 记录 Bridge 模式下的日志信息，包含时间戳和日志内容
 */
interface BridgeLogItem {
  time: string;
  content: string;
}

// 连接重试间隔（毫秒）
const connectRetryInterval = 300;

/**
 * Bridge 状态类型
 * - listening: 正在监听连接
 * - connected: 已连接
 * - disconnected: 意外断开
 * - closed: 已关闭
 */
type BridgeStatus =
  | 'listening'
  | 'connected'
  | 'disconnected' /* disconnected unintentionally */
  | 'closed';

/**
 * Bridge 连接器类
 * 负责管理与本地终端的 Bridge 连接，处理状态变化和消息传递
 */
class BridgeConnector {
  status: BridgeStatus = 'closed';

  // 活动的 Bridge 页面实例
  activeBridgePage: ExtensionBridgePageBrowserSide | null = null;

  /**
   * 构造函数
   * @param onMessage 消息处理回调，接收消息内容和类型
   * @param onBridgeStatusChange 状态变化回调，接收新的状态
   */
  constructor(
    private onMessage: (message: string, type: 'log' | 'status') => void,
    private onBridgeStatusChange: (status: BridgeStatus) => void,
  ) {
    this.status = 'closed';
  }

  /**
   * 设置 Bridge 连接状态并触发回调
   * @param status 新的状态
   */
  setStatus(status: BridgeStatus) {
    this.status = status;
    this.onBridgeStatusChange(status);
  }

  /**
   * 保持监听连接
   * 启动连接监听循环，尝试建立与本地终端的连接
   */
  keepListening() {
    if (this.status === 'listening' || this.status === 'connected') {
      return;
    }

    this.setStatus('listening');

    (async () => {
      while (true) {
        if (this.status === 'connected') {
          await new Promise((resolve) => setTimeout(resolve, 1000));
          continue;
        }

        if (this.status === 'closed') {
          break;
        }

        if (this.status !== 'listening' && this.status !== 'disconnected') {
          throw new Error(`unexpected status: ${this.status}`);
        }

        let activeBridgePage: ExtensionBridgePageBrowserSide | null = null;
        try {
          // 创建新的 Bridge 页面实例
          activeBridgePage = new ExtensionBridgePageBrowserSide(() => {
            if (this.status !== 'closed') {
              this.setStatus('disconnected');
              this.activeBridgePage = null;
            }
          }, this.onMessage);
          await activeBridgePage.connect();
          this.activeBridgePage = activeBridgePage;

          this.setStatus('connected');
        } catch (e) {
          // 连接失败，清理并重试
          this.activeBridgePage?.destroy();
          this.activeBridgePage = null;
          console.warn('failed to setup connection', e);
          await new Promise((resolve) =>
            setTimeout(resolve, connectRetryInterval),
          );
        }
      }
    })();
  }

  /**
   * 停止 Bridge 连接
   * 销毁活动的 Bridge 页面并将状态设为关闭
   */
  async stopConnection() {
    if (this.status === 'closed') {
      console.warn('Cannot stop connection if not connected');
      return;
    }

    if (this.activeBridgePage) {
      await this.activeBridgePage.destroy();
      this.activeBridgePage = null;
    }

    this.setStatus('closed');
  }
}

/**
 * Bridge 组件
 * 展示 Bridge 模式界面，允许用户启动或停止与本地终端的连接
 * 显示连接状态和日志信息
 */
export default function Bridge() {
  // Bridge 状态和任务状态
  const [bridgeStatus, setBridgeStatus] = useState<BridgeStatus>('closed');
  const [taskStatus, setTaskStatus] = useState<string>('');

  // Bridge 日志
  const [bridgeLog, setBridgeLog] = useState<BridgeLogItem[]>([]);

  /**
   * 添加日志条目
   * @param content 日志内容
   */
  const appendBridgeLog = (content: string) => {
    setBridgeLog((prev) => [
      ...prev,
      {
        time: dayjs().format('HH:mm:ss.SSS'),
        content,
      },
    ]);
  };

  // Bridge 连接器引用
  const activeBridgeConnectorRef = useRef<BridgeConnector | null>(
    new BridgeConnector(
      (message, type) => {
        appendBridgeLog(message);
        if (type === 'status') {
          console.log('status tip changed event', type, message);
          setTaskStatus(message);
        }
      },
      (status) => {
        console.log('status changed event', status);
        setTaskStatus('');
        setBridgeStatus(status);
        if (status !== 'connected') {
          appendBridgeLog(`Bridge status changed to ${status}`);
        }
      },
    ),
  );

  // 组件卸载时停止连接
  useEffect(() => {
    return () => {
      activeBridgeConnectorRef.current?.stopConnection();
    };
  }, []);

  /**
   * 停止 Bridge 连接
   */
  const stopConnection = () => {
    activeBridgeConnectorRef.current?.stopConnection();
  };

  /**
   * 启动 Bridge 连接监听
   */
  const startConnection = async () => {
    activeBridgeConnectorRef.current?.keepListening();
  };

  // 根据当前状态确定显示的图标、提示和按钮
  let statusIcon: any;
  let statusTip: string;
  let statusBtn: any;
  if (bridgeStatus === 'closed') {
    statusIcon = iconForStatus('closed');
    statusTip = 'Closed';
    statusBtn = (
      <Button
        type="primary"
        onClick={() => {
          startConnection();
        }}
      >
        Allow connection
      </Button>
    );
  } else if (bridgeStatus === 'listening' || bridgeStatus === 'disconnected') {
    statusIcon = (
      <Spin
        className="bridge-status-icon"
        indicator={<LoadingOutlined spin />}
        size="small"
      />
    );
    statusTip =
      bridgeStatus === 'listening'
        ? 'Listening for connection...'
        : 'Disconnected, listening for a new connection...';
    statusBtn = <Button onClick={stopConnection}>Stop</Button>;
  } else if (bridgeStatus === 'connected') {
    statusIcon = iconForStatus('connected');
    statusTip = taskStatus ? `Connected - ${taskStatus}` : 'Connected';

    statusBtn = (
      <Button
        onClick={() => {
          stopConnection();
        }}
      >
        Stop
      </Button>
    );
  } else {
    statusIcon = iconForStatus('failed');
    statusTip = `Unknown Status - ${bridgeStatus}`;
    statusBtn = null;
  }

  // 准备日志条目，新的日志显示在顶部
  const logs = [...bridgeLog].reverse().map((log, index) => {
    return (
      <div className="bridge-log-item" key={index}>
        <div
          className="bridge-log-item-content"
          style={{
            fontVariantNumeric: 'tabular-nums',
            fontFeatureSettings: 'tnum',
          }}
        >
          {log.time} - {log.content}
        </div>
      </div>
    );
  });

  return (
    <div>
      {/* Bridge 模式说明 */}
      <p>
        In Bridge Mode, you can control this browser by the Midscene SDK running
        in the local terminal. This is useful for interacting both through
        scripts and manually, or to reuse cookies.{' '}
        <a
          href="https://www.midscenejs.com/bridge-mode-by-chrome-extension"
          target="_blank"
          rel="noreferrer"
        >
          More about bridge mode
        </a>
      </p>

      <div className="playground-form-container">
        {/* Bridge 状态显示区域 */}
        <div className="form-part">
          <h3>Bridge Status</h3>
          <div className="bridge-status-bar">
            <div className="bridge-status-text">
              <span className="bridge-status-icon">{statusIcon}</span>
              <span className="bridge-status-tip">{statusTip}</span>
            </div>
            <div className="bridge-status-btn">{statusBtn}</div>
          </div>
        </div>
        {/* Bridge 日志显示区域 */}
        <div className="form-part">
          <h3>
            Bridge Log{' '}
            <Button
              type="text"
              onClick={() => setBridgeLog([])}
              style={{
                marginLeft: '6px',
                display: logs.length > 0 ? 'inline-block' : 'none',
              }}
            >
              clear
            </Button>
          </h3>
          <div className="bridge-log-container">
            {logs.length === 0 ? <p>No logs yet</p> : logs}
          </div>
        </div>
      </div>
    </div>
  );
}
