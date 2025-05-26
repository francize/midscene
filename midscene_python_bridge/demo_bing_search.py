import asyncio
import logging
# from midscene_python_bridge.bridge_mode.agent_cli_side import AgentOverChromeBridge
from bridge_mode.agent_cli_side import AgentOverChromeBridge # Adjusted import for consistency

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

# 设置环境变量
import os
os.environ["OPENAI_API_KEY"] = "33b305a9-ceae-4732-9c2e-2df6b945a46b"
os.environ["OPENAI_BASE_URL"] = "https://ark.cn-beijing.volces.com/api/v3"
os.environ["MIDSCENE_LLM_MODEL"] = "doubao-1.5-ui-tars-250328"
os.environ["MIDSCENE_USE_VLM_UI_TARS"] = "DOUBAO"

logger = logging.getLogger("DemoBingSearch")


async def main():
    """
    主异步函数，用于演示与 MidScene Chrome 扩展的交互。
    它会打开一个新的 Bing 标签页，搜索 "AI 101"，然后断言搜索结果的存在。
    """
    logger.info("开始 demo_bing_search 演示...")

    browser_connected_event = asyncio.Event()
    # browser_disconnected_event = asyncio.Event() # Not strictly needed for this demo's flow

    def on_connect():
        logger.info("Chrome 扩展已连接到 Python 服务器！")
        browser_connected_event.set()
        # browser_disconnected_event.clear()

    def on_disconnect(reason: str):
        logger.warning(f"Chrome 扩展已从 Python 服务器断开。原因: {reason}")
        browser_connected_event.clear()
        # browser_disconnected_event.set()

    agent = AgentOverChromeBridge(
        on_browser_connect=on_connect,
        on_browser_disconnect=on_disconnect
    )

    try:
        logger.info("启动 Python Bridge 服务器...")
        await agent.start()
        logger.info(f"Python BridgeServer 已启动于 http://127.0.0.1:{agent.port}")
        logger.info("请在Chrome扩展中进入Bridge Mode并点击 'Allow connection'。")

        # 等待浏览器连接，设置一个超时
        try:
            logger.info("等待 Chrome 扩展连接 (超时时间 60 秒)...")
            await asyncio.wait_for(browser_connected_event.wait(), timeout=60.0)
            logger.info("Chrome 扩展已成功连接。")
            await asyncio.sleep(1) # 短暂等待，确保连接稳定
        except asyncio.TimeoutError:
            logger.error("等待 Chrome 扩展连接超时。请确保扩展已正确配置并尝试连接。")
            return # 超时则退出

        if not agent.connected:
            logger.warning("未能连接到 Chrome 扩展，后续操作可能失败。")
            # return # 如果未连接，可以选择退出

        target_url = "https://www.bing.com"
        logger.info(f"指示 Chrome 扩展打开新标签页并导航到: {target_url}")
        
        tab_initialized_successfully = False
        try:
            tab_initialized_successfully = await agent.connect_new_tab_with_url(target_url)
            if tab_initialized_successfully:
                 logger.info(f"connect_new_tab_with_url 调用完成，已打开新标签页: {target_url}")
            else:
                logger.warning(f"connect_new_tab_with_url 未能成功初始化标签页。")
        except Exception as e:
            logger.error(f"connect_new_tab_with_url 发生错误: {e}", exc_info=True)
        
        if not tab_initialized_successfully:
            logger.warning("由于无法通过 connect_new_tab_with_url 初始化标签页，后续页面操作很可能失败。")
            # 可以考虑在此处返回或抛出异常
            # return

        search_query = 'type "AI 101" and hit Enter'
        logger.info(f"执行 AI 动作: {search_query}")
        await agent.ai_action(search_query)
        logger.info("AI 动作执行完成。")

        logger.info("等待 3 秒让搜索结果加载...")
        await asyncio.sleep(3)

        assertion_prompt = "there are some search results"
        logger.info(f"执行 AI 断言: {assertion_prompt}")
        await agent.ai_assert(assertion_prompt)
        logger.info("AI 断言成功: 页面上存在搜索结果。")

        logger.info("演示成功完成！")

    except asyncio.CancelledError:
        logger.info("演示任务被取消。")
    except Exception as e:
        logger.error(f"演示过程中发生未捕获的错误: {e}", exc_info=True)
    finally:
        logger.info("正在关闭 AgentOverChromeBridge...")
        await agent.close()
        logger.info("AgentOverChromeBridge 已关闭。演示结束。")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户通过 Ctrl+C 中断了演示脚本。") 