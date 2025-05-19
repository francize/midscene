import { AgentOverChromeBridge } from "@midscene/web/bridge-mode";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
Promise.resolve(
  (async () => {
    const agent = new AgentOverChromeBridge();

    // 这个方法将连接到你的桌面 Chrome 的新标签页
    // 记得启动你的 Chrome 插件，并点击 'allow connection' 按钮。否则你会得到一个 timeout 错误
    await agent.connectNewTabWithUrl("https://www.bing.com");

    // 这些方法与普通 Midscene agent 相同
    await agent.ai('type "AI 101" and hit Enter');
    await sleep(3000);

    await agent.aiAssert("there are some search results");
    await agent.destroy();
  })()
); 