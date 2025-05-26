#!/usr/bin/env python3
"""简单的MidScene Python Bridge演示脚本"""

import asyncio
import logging
import base64
import json
from pathlib import Path
from datetime import datetime

from bridge_mode.agent_cli_side import AgentOverChromeBridge

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler() # 输出到控制台
    ]
)
# 将特定库的日志级别调低，以减少不必要的输出
logging.getLogger("socketio.server").setLevel(logging.WARNING)
logging.getLogger("engineio.server").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger("DemoSimple")

async def main():
    logger.info("启动MidScene Python Bridge演示...")
    
    browser_connected_event = asyncio.Event()
    browser_disconnected_event = asyncio.Event()

    def on_connect():
        logger.info("浏览器已连接到Python服务器！现在可以进行调用了。")
        browser_connected_event.set()
        browser_disconnected_event.clear() # 如果之前是断开的，重置断开事件

    def on_disconnect(reason: str):
        logger.warning(f"浏览器已从Python服务器断开。原因: {reason}")
        browser_connected_event.clear()
        browser_disconnected_event.set()

    # 初始化AgentOverChromeBridge，它将启动服务器
    agent = AgentOverChromeBridge(
        on_browser_connect=on_connect,
        on_browser_disconnect=on_disconnect
    )

    try:
        # 启动服务器
        await agent.start()
        logger.info(f"Python BridgeServer已启动于 http://127.0.0.1:{agent.port}")
        logger.info("请在Chrome扩展中进入Bridge Mode并点击 'Allow connection'。")

        # 等待浏览器连接，设置一个超时
        try:
            await asyncio.wait_for(browser_connected_event.wait(), timeout=60.0) 
            logger.info("与浏览器成功建立连接。在发送命令前稍作等待...")
            await asyncio.sleep(2) # 增加2秒延迟
        except asyncio.TimeoutError:
            logger.error("等待浏览器连接超时。请确保Chrome扩展已正确配置并尝试连接。")
            return # 超时则退出

        if agent.connected:
            logger.info("与浏览器成功建立连接!")
            
            connect_url = "https://example.com/"
            logger.info(f"尝试使用 connect_new_tab_with_url 打开并连接到: {connect_url}")
            tab_initialized_successfully = False
            try:
                tab_initialized_successfully = await agent.connect_new_tab_with_url(connect_url)
                if tab_initialized_successfully:
                    logger.info(f"connect_new_tab_with_url 调用完成，认为标签页可能已连接。")
                else:
                    logger.warning(f"connect_new_tab_with_url 未能成功初始化标签页。")
            except Exception as e: #理论上内部已经处理了，这里是备用
                logger.error(f"在 demo_simple.py 中捕获到 connect_new_tab_with_url 异常: {e}")

            if not tab_initialized_successfully:
                logger.warning("由于无法通过 connect_new_tab_with_url 初始化标签页，后续页面操作很可能失败。")
            
            logger.info("开始执行页面操作...")
            
            # 1. 获取浏览器版本
            try:
                version = await agent.version()
                logger.info(f"获取到浏览器端桥接版本: {version}")
            except Exception as e:
                logger.error(f"调用 agent.version() 失败: {e}")

            # 2. 导航到示例页面 (现在由 connect_new_tab_with_url 完成初始导航)
            try:
                # test_url = "https://example.com" # 不再需要显式导航，已由connect_new_tab完成
                # logger.info(f"正在导航到: {test_url}")
                # await agent.navigate(test_url) # 
                await asyncio.sleep(1) # 短暂等待，确保页面状态稳定
                
                current_url = await agent.get_url()
                logger.info(f"当前页面URL: {current_url}")
                
                title = await agent.get_title()
                logger.info(f"页面标题: {title}")
            except Exception as e:
                logger.error(f"获取URL或标题失败: {e}")

            # 3. 执行JavaScript获取页面上的所有链接 (使用JSON.stringify)
            js_get_links = "JSON.stringify(Array.from(document.querySelectorAll('a')).map(a => ({ text: a.textContent.trim(), href: a.href })))"
            logger.info(f"执行JS (获取链接): {js_get_links[:100]}...")
            links_json_str = await agent.evaluate(js_get_links)
            if links_json_str and isinstance(links_json_str, str):
                try:
                    links = json.loads(links_json_str)
                    logger.info(f"页面上的链接 (解析后): {links}")
                except json.JSONDecodeError:
                    logger.error(f"解析链接JSON失败: {links_json_str}")
            else:
                logger.info(f"页面上的链接 (原始返回): {links_json_str}")

            logger.info("演示操作完成。")
        else:
            logger.warning("未能连接到浏览器，跳过操作。")

    except ConnectionError as e:
        logger.error(f"连接错误: {e}")
    except asyncio.CancelledError:
        logger.info("演示任务被取消。")
    except Exception as e:
        logger.error(f"演示过程中发生未捕获的错误: {e}", exc_info=True)
    finally:
        logger.info("关闭Python BridgeServer...")
        await agent.close()
        logger.info("演示结束。")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户中断了演示脚本。") 