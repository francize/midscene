# West Browser Automation MCP Plugin

**West 浏览器自动化插件**，基于Model Context Protocol (MCP)协议实现，使用 FastMCP 框架开发，支持远程控制浏览器导航、内容获取和元素交互。

## 功能特性

本插件提供以下核心功能：

### 🌐 导航控制
- **navigate**: 导航到指定的URL地址
- 支持多用户浏览器会话管理
- 自动处理页面加载等待

### 📄 内容获取
- **getPageContent**: 获取当前标签页的页面内容和截图
- 支持可选的页面截图获取
- 返回页面标题、URL和文本内容

### 🖱️ 元素交互
- **clickElement**: 点击页面上的指定元素
- 支持CSS选择器和元素描述
- 智能元素定位和点击操作

## 架构设计

```
┌─────────────────┐    MCP Protocol    ┌─────────────────┐    HTTP API    ┌─────────────────┐
│   MCP Client    │ ←─────────────────→ │  MCP Plugin     │ ──────────────→ │ West Bridge │
│  (Claude/GPT)   │                    │  (FastMCP)      │                │    Service      │
└─────────────────┘                    └─────────────────┘                └─────────────────┘
                                               │                                     │
                                               │                                     │
                                               ▼                                     ▼
                                        ┌─────────────────┐                ┌─────────────────┐
                                        │   Plugin        │                │   Browser       │
                                        │  Marketplace    │                │   Instances     │
                                        └─────────────────┘                └─────────────────┘
```

### 技术栈
- **FastMCP**: 简化的 MCP 服务器框架
- **Starlette**: 轻量级 ASGI 框架
- **httpx**: 异步 HTTP 客户端
- **Docker**: 容器化部署

## 快速开始

### 1. 环境要求

- Python 3.11+
- Docker (用于容器化部署)
- West Bridge Service (需要单独部署)

### 2. 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export WEST_BRIDGE_URL=http://localhost:3001

# 直接运行服务器 (SSE模式)
python server.py

# 或者使用插件广场模式
python main.py
```


### 3. 插件广场部署

将插件目录打包为 zip 文件上传到插件广场，系统会自动：
1. 读取 `manifest.yaml` 获取插件信息
2. 构建Docker镜像
3. 启动容器实例在8000端口
4. 通过 SSE 协议提供 MCP 服务

## 工具说明

### navigate 导航工具
```python
await navigate(
    username="user123", 
    url="https://example.com"
)
```

### getPageContent 获取页面内容
```python
await getPageContent(
    username="user123", 
    includeScreenshot=True
)
```

### clickElement 点击元素
```python
await clickElement(
    username="user123", 
    selector="#submit-button"
)
```

## 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `WEST_BRIDGE_URL` | `http://localhost:3001` | West Bridge服务地址 |

### 插件配置

```yaml
# manifest.yaml
author: "nashe"
name: "west-mcp-browser-automation"
description: "West 浏览器自动化插件，支持远程控制浏览器导航、内容获取和元素交互"
resource:
  memory: 2097152  # 2MB内存限制
version: 0.0.1
```

## 文件结构

```
west/midscene_mcp_plugin/
├── manifest.yaml      # 插件描述文件
├── tools.json         # 工具声明文件 (用于插件广场)
├── requirements.txt   # Python依赖
├── main.py           # 插件广场入口文件 (Starlette应用)
├── server.py         # FastMCP服务器实现
├── Dockerfile        # 容器构建文件
└── README.md         # 说明文档
```

## 开发指南

### 添加新工具

在 `server.py` 中使用 `@mcp.tool()` 装饰器非常简单：

```python
@mcp.tool()
async def newTool(param1: str, param2: int = 10) -> str:
    """
    新工具的描述
    
    Args:
        param1: 参数1的描述
        param2: 参数2的描述
        
    Returns:
        返回结果的描述
    """
    # 实现你的逻辑
    return "工具执行结果"
```

FastMCP 会自动：
- 根据函数签名生成工具的参数schema
- 处理MCP协议通信
- 提供SSE端点

### 本地测试

```bash
# 使用 mcp 工具测试
mcp dev server.py

# 或者直接运行并访问 http://localhost:8000/sse
python server.py
```

## 故障排除

### 常见问题

1. **无法连接到Bridge服务**
   - 检查 `WEST_BRIDGE_URL` 环境变量
   - 确认Bridge服务是否正常运行

2. **工具调用失败**
   - 检查传入参数是否正确
   - 查看服务日志获取详细错误信息

3. **容器启动失败**
   - 检查8000端口是否被占用
   - 查看容器日志排查启动问题

### 日志查看

```bash
# 查看容器日志
docker logs west-mcp

# 实时查看日志
docker logs -f west-mcp
```

## 参考资料

- [MCP 中文入门指南](https://github.com/liaokongVFX/MCP-Chinese-Getting-Started-Guide)
- [Model Context Protocol 官方文档](https://modelcontextprotocol.io/)
- [FastMCP 使用说明](https://github.com/modelcontextprotocol/python-sdk)

## 许可证

本项目采用 MIT 许可证。 