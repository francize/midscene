import type {
  ChromePageDestroyOptions,
  KeyboardAction,
  MouseAction,
} from '@/page';
import { assert } from '@midscene/shared/utils';
import ChromeExtensionProxyPage from '../chrome-extension/page';
import {
  type BridgeConnectTabOptions,
  BridgeEvent,
  DefaultBridgeServerPort,
  KeyboardEvent,
  MouseEvent,
} from './common';
import { BridgeClient } from './io-client';
import { PageAgent } from '../common/agent';

declare const __VERSION__: string;

export class ExtensionBridgePageBrowserSide extends ChromeExtensionProxyPage {
  public bridgeClient: BridgeClient | null = null;

  private destroyOptions?: ChromePageDestroyOptions;

  private newlyCreatedTabIds: number[] = [];

  private agent: PageAgent<this>;

  constructor(
    public onDisconnect: () => void = () => {},
    public onLogMessage: (
      message: string,
      type: 'log' | 'status',
    ) => void = () => {},
    forceSameTabNavigation = true,
  ) {
    super(forceSameTabNavigation);
    this.agent = new PageAgent<this>(this, {
      generateReport: false,
      autoPrintReportMsg: false,
    });
  }

  private async setupBridgeClient() {
    this.bridgeClient = new BridgeClient(
      `ws://172.22.0.3:${DefaultBridgeServerPort}`,
      async (method, args: any[]) => {
        console.log('bridge call from cli side', method, args);
        if (method === BridgeEvent.ConnectNewTabWithUrl) {
          return this.connectNewTabWithUrl.apply(
            this,
            args as unknown as [string],
          );
        }

        if (method === BridgeEvent.GetBrowserTabList) {
          return this.getBrowserTabList.apply(this, args as any);
        }

        if (method === BridgeEvent.SetActiveTabId) {
          return this.setActiveTabId.apply(this, args as any);
        }

        if (method === BridgeEvent.ConnectCurrentTab) {
          return this.connectCurrentTab.apply(this, args as any);
        }

        if (method === BridgeEvent.UpdateAgentStatus) {
          return this.onLogMessage(args[0] as string, 'status');
        }

        if (method === BridgeEvent.AiTap) {
          const [naturalLanguagePrompt] = args as [string];
          this.onLogMessage(`AI Tap received for: "${naturalLanguagePrompt}"`, 'log');
          try {
            const result = await this.agent.aiTap(naturalLanguagePrompt);
            this.onLogMessage(`AI Tap successful for: "${naturalLanguagePrompt}"`, 'log');
            return result;
          } catch (error: any) {
            this.onLogMessage(`AI Tap failed for "${naturalLanguagePrompt}": ${error.message}`, 'log');
            throw error;
          }
        }

        const tabId = await this.getActiveTabId();
        if (!tabId || tabId === 0) {
          throw new Error('no tab is connected');
        }

        if (method.startsWith(MouseEvent.PREFIX)) {
          const actionName = method.split('.')[1] as keyof MouseAction;
          if (typeof this.mouse[actionName] === 'function') {
            return (this.mouse[actionName] as Function).apply(this.mouse, args as any);
          }
          throw new Error(`Unknown mouse action: ${actionName}`);
        }

        if (method.startsWith(KeyboardEvent.PREFIX)) {
          const actionName = method.split('.')[1] as keyof KeyboardAction;
          if (typeof this.keyboard[actionName] === 'function') {
            return (this.keyboard[actionName] as Function).apply(this.keyboard, args as any);
          }
          throw new Error(`Unknown keyboard action: ${actionName}`);
        }

        try {
          if (typeof (this as any)[method] === 'function') {
            return (this as any)[method](...args);
          }
          throw new Error(`Method ${method} not found on this page object.`);
        } catch (e) {
          const errorMessage = e instanceof Error ? e.message : 'Unknown error';
          console.error('error calling method', method, args, e);
          this.onLogMessage(
            `Error calling method: ${method}, ${errorMessage}`,
            'log',
          );
          throw new Error(errorMessage, { cause: e });
        }
      },
      () => {
        return this.destroy();
      },
    );
    await this.bridgeClient.connect();
    this.onLogMessage(
      `Bridge connected, cli-side version v${this.bridgeClient.serverVersion}, browser-side version v${__VERSION__}`,
      'log',
    );
  }

  public async connect() {
    return await this.setupBridgeClient();
  }

  public async connectNewTabWithUrl(
    url: string,
    options: BridgeConnectTabOptions = {
      forceSameTabNavigation: true,
    },
  ) {
    const tab = await chrome.tabs.create({ url });
    const tabId = tab.id;
    assert(tabId, 'failed to get tabId after creating a new tab');

    this.onLogMessage(`Creating new tab: ${url}`, 'log');
    this.newlyCreatedTabIds.push(tabId);

    if (options?.forceSameTabNavigation) {
      this.forceSameTabNavigation = true;
    }

    await this.setActiveTabId(tabId);
  }

  public async connectCurrentTab(
    options: BridgeConnectTabOptions = {
      forceSameTabNavigation: true,
    },
  ) {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    console.log('current tab', tabs);
    const tabId = tabs[0]?.id;
    assert(tabId, 'failed to get tabId');

    this.onLogMessage(`Connected to current tab: ${tabs[0]?.url}`, 'log');

    if (options?.forceSameTabNavigation) {
      this.forceSameTabNavigation = true;
    }

    await this.setActiveTabId(tabId);
  }

  public async setDestroyOptions(options: ChromePageDestroyOptions) {
    this.destroyOptions = options;
  }

  async destroy() {
    if (this.destroyOptions?.closeTab && this.newlyCreatedTabIds.length > 0) {
      this.onLogMessage('Closing all newly created tabs by bridge...', 'log');
      for (const tabId of this.newlyCreatedTabIds) {
        await chrome.tabs.remove(tabId);
      }
      this.newlyCreatedTabIds = [];
    }

    await super.destroy();

    if (this.bridgeClient) {
      this.bridgeClient.disconnect();
      this.bridgeClient = null;
      this.onDisconnect();
    }
  }
}
