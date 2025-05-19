#!/usr/bin/env python3
"""MidScene Python Bridge演示脚本"""

import asyncio
import logging

from bridge_mode import AgentOverChromeBridge

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Demo")

async def demo():
    """演示脚本"""
    logger.info("创建ChromeBridge实例...")
    agent = AgentOverChromeBridge()

    try:
        logger.info("连接到新标签页...")
        # 这个方法将连接到你的桌面Chrome的新标签页
        # 记得启动你的Chrome插件，并点击'allow connection'按钮，否则会得到超时错误
        await agent.connectNewTabWithUrl("https://www.bing.com")
        logger.info("成功连接到新标签页并导航到Bing")
        
        # 与普通Midscene agent相同的方法
        logger.info("执行AI操作: type \"AI 101\" and hit Enter")
        await agent.ai('type "AI 101" and hit Enter')
        
        # 等待3秒，观察结果
        logger.info("等待3秒...")
        await asyncio.sleep(3)
        
        logger.info("执行AI断言...")
        await agent.aiAssert("there are some search results")
    except Exception as e:
        logger.error(f"演示过程中发生错误: {e}")
    finally:
        logger.info("销毁连接...")
        await agent.destroy(True)  # 参数为True表示关闭标签页
        logger.info("演示完成")

if __name__ == "__main__":
    asyncio.run(demo()) 