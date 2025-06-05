"""
WEST Browser Automation MCP Server

使用 FastMCP 实现的 west 浏览器自动化 MCP 服务器
支持远程控制浏览器导航、内容获取和元素交互
"""

import httpx
import os
import logging
from mcp.server import FastMCP

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastMCP 应用实例
mcp = FastMCP('west-mcp-browser-automation', port=8000)

# 默认的 west Bridge 服务地址
BRIDGE_URL = os.getenv("WEST_BRIDGE_URL", "http://172.22.0.3:9091")

async def make_bridge_request(method: str, endpoint: str, data: dict) -> dict:
    """向 west Bridge 服务发送 HTTP 请求"""
    url = f"{BRIDGE_URL}{endpoint}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                response = await client.get(url, params=data)
            else:
                response = await client.post(url, json=data)
            
            response.raise_for_status()
            return response.json()
            
    except httpx.RequestError as e:
        logger.error(f"请求错误: {e}")
        raise Exception(f"无法连接到 west Bridge 服务: {e}")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP错误: {e}")
        raise Exception(f"Bridge 服务返回错误: {e.response.status_code}")

@mcp.tool()
async def navigate(username: str, url: str) -> str:
    """
    导航到指定的URL地址
    
    Args:
        username: 用户名，用于识别目标浏览器
        url: 要导航到的URL地址
        
    Returns:
        导航操作的结果描述
    """
    try:
        response = await make_bridge_request("POST", "/api/navigate", {
            "username": username,
            "url": url
        })
        
        if response.get("success"):
            return f"成功导航到 {url}"
        else:
            error_msg = response.get("error", "未知错误")
            return f"导航失败: {error_msg}"
            
    except Exception as e:
        return f"导航请求失败: {str(e)}"

@mcp.tool()
async def getPageContent(username: str, includeScreenshot: bool = False) -> str:
    """
    获取当前标签页的页面内容和截图
    
    Args:
        username: 用户名，用于识别目标浏览器
        includeScreenshot: 是否包含页面截图
        
    Returns:
        页面内容的描述，包括标题、URL和文本内容
    """
    try:
        response = await make_bridge_request("GET", "/api/page-content", {
            "username": username,
            "includeScreenshot": includeScreenshot
        })
        
        if response.get("success"):
            content = response.get("data", {})
            result_text = f"页面标题: {content.get('title', 'N/A')}\n"
            result_text += f"页面URL: {content.get('url', 'N/A')}\n"
            result_text += f"页面内容: {content.get('content', 'N/A')}"
            
            if includeScreenshot and content.get('screenshot'):
                result_text += f"\n截图已获取 (长度: {len(content['screenshot'])} 字符)"
            
            return result_text
        else:
            error_msg = response.get("error", "未知错误")
            return f"获取页面内容失败: {error_msg}"
            
    except Exception as e:
        return f"获取页面内容请求失败: {str(e)}"

@mcp.tool()
async def clickElement(username: str, selector: str) -> str:
    """
    点击页面上的指定元素
    
    Args:
        username: 用户名，用于识别目标浏览器
        selector: CSS选择器或元素描述
        
    Returns:
        点击操作的结果描述
    """
    try:
        response = await make_bridge_request("POST", "/api/click", {
            "username": username,
            "selector": selector
        })
        
        if response.get("success"):
            return f"成功点击元素: {selector}"
        else:
            error_msg = response.get("error", "未知错误")
            return f"点击元素失败: {error_msg}"
            
    except Exception as e:
        return f"点击元素请求失败: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport='sse') 