# MidScene Python Bridge

这是MidScene Chrome扩展的Python客户端实现，可以让你通过Python代码控制Chrome浏览器进行自动化操作。

## 前提条件

1. 安装MidScene Chrome扩展：从 [Chrome Web Store](https://chromewebstore.google.com/detail/midscenejs/gbldofcpkknbggpkmbdaefngejllnief) 下载
2. 确保扩展已打开并切换到"Bridge Mode"模式
3. 点击"Allow Connection"（允许连接）按钮，如下图所示：
   ![Bridge Mode](https://lf3-static.bytednsdoc.com/obj/eden-cn/ozpmyhn_lm_hymuPild/ljhwZthlaukjlkulzlp/midscene/image.png)

## 安装

```bash
cd midscene_python_bridge
pip install -r requirements.txt
```

## 使用方法

确保你已安装并启动了MidScene Chrome扩展，点击了"允许连接"按钮，然后运行以下代码：

```python
import asyncio
from bridge_mode import AgentOverChromeBridge

async def main():
    # 创建agent
    agent = AgentOverChromeBridge()
    
    try:
        # 连接到新标签页并导航到bing.com
        await agent.connectNewTabWithUrl("https://www.bing.com")
        
        # 执行AI指令
        await agent.ai('type "hello world" and hit Enter')
        
        # 等待一些时间
        await asyncio.sleep(3)
        
        # 执行断言
        await agent.aiAssert("there are some search results")
    finally:
        # 销毁连接，关闭标签页
        await agent.destroy(True)

if __name__ == "__main__":
    asyncio.run(main())
```

## 演示

运行演示脚本：

```bash
python demo_simple.py
```

## 功能

- 连接到Chrome扩展
- 打开新标签页或连接到当前标签页
- 执行AI指令控制浏览器
- 执行鼠标和键盘操作
- 管理标签页
- 执行断言

## 结构

- `bridge_mode/` - 桥接模式的实现
  - `agent_cli_side.py` - Agent客户端代理实现
  - `io_client.py` - Socket.IO客户端实现
  - `page_cli_side.py` - 页面客户端代理实现
  - `common.py` - 常量和公共定义

## 常见问题

### 连接失败

如果看到"无法连接到Chrome扩展"错误，请确保：

1. MidScene Chrome扩展已打开
2. 切换到"Bridge Mode"（桥接模式）标签页
3. 点击"Allow Connection"（允许连接）按钮
4. 确保端口3766未被其他程序占用

### 端口冲突问题

如果3766端口被占用，可以用以下命令释放：

```bash
# For macOS/Linux:
lsof -i:3766 | awk 'NR>1 {print $2}' | xargs -r kill -9

# For Windows:
FOR /F "tokens=5" %i IN ('netstat -ano ^| findstr :3766') DO taskkill /F /PID %i
```

## 开发笔记

此库使用Python的`python-socketio`库与Chrome扩展通信，参考了原始TypeScript实现。 