import { AgentOverChromeBridge } from "@midscene/web/bridge-mode";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
Promise.resolve(
  (async () => {
    console.log("创建ChromeBridge实例...");
    const agent = new AgentOverChromeBridge();

    console.log("连接到新标签页...");
    // 这个方法将连接到你的桌面 Chrome 的新标签页
    // 记得启动你的 Chrome 插件，并点击 'allow connection' 按钮
    await agent.connectNewTabWithUrl("https://www.bing.com");
    console.log("成功连接到新标签页并导航到Bing");
    
    // 等待5秒，观察页面
    console.log("等待5秒...");
    await sleep(5000);
    
    console.log("销毁连接...");
    await agent.destroy(true); // 参数为true表示关闭标签页
    console.log("演示完成");
  })()
); 