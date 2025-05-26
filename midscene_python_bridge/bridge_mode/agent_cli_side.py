"""Agent客户端代理实现，参考原TypeScript版本"""

import asyncio
import logging
from typing import TypedDict, List, Tuple, Dict, Any, Optional, Callable, Union, Literal
import json # For parsing evaluate results if they are JSON strings
import uvicorn # 用于运行ASGI应用
import os # Added for environment variables
import openai # Added for OpenAI API calls

from .types import (
    WebElementInfo,
    ElementTreeNode,
    WebUIContext,
    PlanningAction,
    PlanResponse,
    InsightAssertionResponse
)

from .ai_tools import (
    build_planning_system_prompt_messages,
    build_planning_user_prompt_message,
    describe_ui_context_for_llm,
    build_assertion_system_prompt_messages,
    build_assertion_user_prompt_message
)

from .common import (
    BridgeEvent,
    BridgeCallTimeout,
    DefaultBridgeServerPort
)
from .io_server import BridgeServer # 导入新的BridgeServer

logger = logging.getLogger("AgentBridge")

# --- Original Data Structures (renamed to avoid conflict) ---
class OriginalWebElementInfo(TypedDict, total=False):
    id: str
    rect: Dict[str, int]
    center: Tuple[int, int]
    content: str # This might be used for 'description' in the new model
    attributes: Dict[str, Any]
    locator: Optional[str]
    indexId: int

class OriginalElementTreeNode(TypedDict, total=False):
    node: Optional[OriginalWebElementInfo]
    children: List['OriginalElementTreeNode']

class OriginalWebUIContext(TypedDict, total=False):
    content: List[OriginalWebElementInfo] # Flat list of elements from older version
    tree: OriginalElementTreeNode      # Tree structure from older version
    size: Dict[str, Union[int, float]]
    screenshotBase64: str
    url: str
    title: Optional[str] # Changed from NotRequired to Optional for Python 3.10 compatibility

# --- AI-aligned Data Structures (as defined in types.py) ---
# These are now imported from types.py

# --- PythonInsight Class (AI交互层) ---
class PythonInsight:
    def __init__(self, agent: 'AgentOverChromeBridge'):
        self.agent = agent
        self.logger = logging.getLogger("PythonInsight")
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.openai_base_url = os.environ.get("OPENAI_BASE_URL")
        self.llm_model_name = os.environ.get("MIDSCENE_LLM_MODEL", "gpt-3.5-turbo-1106") # Default model

        if not self.openai_api_key:
            self.logger.warning("OPENAI_API_KEY environment variable not found. LLM calls will fail.")
            # Depending on strictness, could raise an error here
        
        try:
            self.client = openai.OpenAI(api_key=self.openai_api_key, base_url=self.openai_base_url)
            self.logger.info(f"OpenAI client initialized. Using model: {self.llm_model_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI client: {e}. LLM calls will likely fail.")
            self.client = None # type: ignore

    async def _call_llm(self, messages: List[Dict[str, str]], purpose: str) -> Optional[str]:
        if not self.client or not self.openai_api_key:
            self.logger.error(f"OpenAI client not initialized or API key missing. Cannot make LLM call for {purpose}.")
            return None
        try:
            self.logger.info(f"Sending request to OpenAI for {purpose} using model {self.llm_model_name}...")
            chat_completion = await asyncio.to_thread(
                self.client.chat.completions.create, # type: ignore
                model=self.llm_model_name,
                messages=messages # type: ignore
            )
            
            if chat_completion.choices and chat_completion.choices[0].message:
                response_content = chat_completion.choices[0].message.content
                self.logger.info(f"Received LLM response for {purpose}: {response_content}")
                
                # Log token usage if available
                if chat_completion.usage:
                    self.logger.info(f"LLM Token Usage ({purpose}): ")
                    self.logger.info(f"  Prompt tokens: {chat_completion.usage.prompt_tokens}")
                    self.logger.info(f"  Completion tokens: {chat_completion.usage.completion_tokens}")
                    self.logger.info(f"  Total tokens: {chat_completion.usage.total_tokens}")
                return response_content
            else:
                self.logger.error(f"LLM response for {purpose} is empty or malformed: {chat_completion}")
                return None
        except openai.APIError as e: # Catch OpenAI specific API errors
            self.logger.error(f"OpenAI API error during {purpose}: {e}", exc_info=True)
            # Specific error handling (e.g. rate limits, auth issues)
            if isinstance(e, openai.RateLimitError):
                self.logger.error("OpenAI API rate limit exceeded.")
            elif isinstance(e, openai.AuthenticationError):
                self.logger.error("OpenAI API authentication error. Check your API key.")
            # Add more specific error handling as needed
            return None
        except Exception as e:
            self.logger.error(f"Generic error during LLM call for {purpose}: {e}", exc_info=True)
            return None

    async def plan(self, user_instruction: str, context: WebUIContext, log: Optional[str] = None, action_context: Optional[str] = None, page_type: str = "chrome-extension-proxy") -> PlanResponse:
        self.logger.info(f"PythonInsight.plan called for: '{user_instruction}'")
        
        ui_context_str = describe_ui_context_for_llm(context)
        system_messages = build_planning_system_prompt_messages()
        user_message = build_planning_user_prompt_message(task=user_instruction, ui_context_str=ui_context_str)
        full_prompt_messages = system_messages + [user_message]
        
        self.logger.info("---- Generated Planning Prompt Messages (for LLM) ----")
        # Log the messages part of the prompt (could be very verbose)
        # self.logger.debug(json.dumps(full_prompt_messages, indent=2))
        self.logger.info("Prompt messages generated (see DEBUG logs for full prompt if enabled).")
        self.logger.info("----------------------------------------------------")

        llm_response_str = await self._call_llm(full_prompt_messages, "planning")

        if llm_response_str is None:
            return PlanResponse(actions=[], reasoning="Error: LLM call failed or returned no content for planning.")

        try:
            parsed_llm_response = json.loads(llm_response_str)
            if "actions" not in parsed_llm_response or not isinstance(parsed_llm_response["actions"], list):
                raise ValueError("LLM response JSON must contain an 'actions' list.")
            for action_item in parsed_llm_response["actions"]:
                if not isinstance(action_item, dict) or "type" not in action_item:
                    raise ValueError(f"Each action in LLM response must be a dict and have a 'type': {action_item}")
            if "reasoning" not in parsed_llm_response or not isinstance(parsed_llm_response["reasoning"], str):
                 self.logger.warning("LLM plan response JSON is missing 'reasoning' string. Adding a default one.")
                 parsed_llm_response["reasoning"] = "No reasoning provided by LLM."

            response: PlanResponse = parsed_llm_response # type: ignore
            self.logger.info(f"Successfully parsed LLM response for planning: {response}")
            return response
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON from LLM for planning: {e}. Raw response: '{llm_response_str}'")
            return PlanResponse(actions=[], reasoning=f"Error: Could not parse LLM JSON for planning - {e}")
        except ValueError as e:
            self.logger.error(f"LLM JSON does not conform to PlanResponse structure: {e}. Raw response: '{llm_response_str}'")
            return PlanResponse(actions=[], reasoning=f"Error: LLM JSON invalid for PlanResponse - {e}")

    async def assert_method(self, assertion_task: str, context: WebUIContext) -> InsightAssertionResponse:
        self.logger.info(f"PythonInsight.assert_method called for: '{assertion_task}'")

        ui_context_str = describe_ui_context_for_llm(context) 
        system_messages = build_assertion_system_prompt_messages()
        user_message = build_assertion_user_prompt_message(assertion_task=assertion_task, ui_context_str=ui_context_str)
        full_prompt_messages = system_messages + [user_message]

        self.logger.info("---- Generated Assertion Prompt Messages (for LLM) ----")
        # self.logger.debug(json.dumps(full_prompt_messages, indent=2))
        self.logger.info("Assertion prompt messages generated (see DEBUG logs for full prompt if enabled).")
        self.logger.info("-----------------------------------------------------")
        
        llm_response_str = await self._call_llm(full_prompt_messages, "assertion")

        if llm_response_str is None:
            return InsightAssertionResponse(passed=False, reason="Error: LLM call failed or returned no content for assertion.")

        try:
            parsed_llm_response = json.loads(llm_response_str)
            if "passed" not in parsed_llm_response or not isinstance(parsed_llm_response["passed"], bool):
                raise ValueError("LLM response JSON must contain a boolean 'passed' field.")
            if "reason" not in parsed_llm_response or not isinstance(parsed_llm_response["reason"], str):
                raise ValueError("LLM response JSON must contain a string 'reason' field.")
                
            response: InsightAssertionResponse = parsed_llm_response # type: ignore
            self.logger.info(f"Successfully parsed LLM response for assertion: {response}")
            return response
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON from LLM for assertion: {e}. Raw response: '{llm_response_str}'")
            return InsightAssertionResponse(passed=False, reason=f"Error: Could not parse LLM JSON for assertion - {e}")
        except ValueError as e:
            self.logger.error(f"LLM JSON does not conform to InsightAssertionResponse structure: {e}. Raw response: '{llm_response_str}'")
            return InsightAssertionResponse(passed=False, reason=f"Error: LLM JSON invalid for InsightAssertionResponse - {e}")

# --- PageTaskExecutor Class (任务执行器) ---
class PageTaskExecutor:
    def __init__(self, agent: 'AgentOverChromeBridge', insight: PythonInsight):
        self.agent = agent
        self.insight = insight
        self.logger = logging.getLogger("PageTaskExecutor")

    async def _execute_plan_action(self, action: PlanningAction, current_context: WebUIContext):
        action_type = action.get("type")
        element_id = action.get("element_id")
        value = action.get("value") # type: ignore
        reasoning = action.get("reasoning", "No reasoning provided.")

        self.logger.info(f"Executing action: {action_type}, Element ID: {element_id}, Value: {value}, Reasoning: '{reasoning}'")

        if action_type == "Input":
            if isinstance(value, str):
                # 如果有 element_id，理想情况下应该先聚焦或确保输入到该元素。
                # 目前 AgentOverChromeBridge.keyboard_type 是全局的。
                # 后续可能需要 agent.focus_element(element_id) 或 agent.type_into_element(element_id, value)
                if element_id:
                    self.logger.info(f"Input action targets element '{element_id}'. Current keyboard_type is global.")
                await self.agent.keyboard_type(value)
            else:
                self.logger.error(f"Input action requires string 'value', got: {value}")
                raise ValueError("Input action 'value' must be a string.")

        elif action_type == "KeyboardPress":
            if isinstance(value, str):
                await self.agent.keyboard_press(value)
            else:
                self.logger.error(f"KeyboardPress action requires string 'value' (key name), got: {value}")
                raise ValueError("KeyboardPress action 'value' (key name) must be a string.")
        
        elif action_type == "Tap":
            if element_id:
                # Tap动作需要将 element_id 转换为坐标，或者桥接端支持按ID点击。
                # 当前 AgentOverChromeBridge.mouse_click 需要 x, y 坐标。
                # 这部分逻辑需要细化：如何从 element_id 得到点击坐标？
                # 1. 从 current_context.elements_tree 查找 element_id 的 rect/center。
                # 2. 或者桥接端增加 click_element_by_id(element_id) 方法。
                # For now, we'll log a warning and skip if not easily convertible.
                self.logger.warning(f"Tap action for element_id '{element_id}' requires coordinates. Not implemented yet for direct ID tap.")
                # Example placeholder for future: 
                # element_to_tap = self._find_element_in_context(element_id, current_context)
                # if element_to_tap and element_to_tap.get('center'):
                #    x, y = element_to_tap['center']
                #    await self.agent.mouse_click(x, y)
                # else:
                #    raise NotImplementedError(f"Cannot find element '{element_id}' or its coordinates for Tap action.")
                raise NotImplementedError(f"Tap action by element_id '{element_id}' needs coordinate resolution or direct bridge support.")
            elif isinstance(value, dict) and 'x' in value and 'y' in value: # 假设value可以是坐标
                await self.agent.mouse_click(int(value['x']), int(value['y']))
            else:
                self.logger.error(f"Tap action requires 'element_id' or coordinate 'value' ({{x, y}}), got: {action}")
                raise ValueError("Invalid Tap action parameters.")

        elif action_type == "Navigate":
            if isinstance(value, str):
                await self.agent.navigate(value)
            else:
                self.logger.error(f"Navigate action requires string 'value' (URL), got: {value}")
                raise ValueError("Navigate action 'value' (URL) must be a string.")

        elif action_type == "Scroll":
            # value should be a dict like {"direction": "down", "amount": "small"} or {"direction": "up", "element_id": "scrollable_div"}
            if isinstance(value, dict):
                direction = value.get("direction")
                # amount = value.get("amount", "small") # 'small'/'large' or pixels
                # scroll_element_id = value.get("element_id", element_id) # Scroll specific element or page
                
                # This needs mapping to agent.scroll_up/down/left/right or mouse_wheel
                # For simplicity, only page scroll down/up for now
                if direction == "down":
                    await self.agent.mouse_wheel(0, 200) # Simulate scroll down
                elif direction == "up":
                    await self.agent.mouse_wheel(0, -200) # Simulate scroll up
                # elif direction == "left":
                #     await self.agent.mouse_wheel(-200, 0) # Simulate scroll left
                # elif direction == "right":
                #     await self.agent.mouse_wheel(200, 0) # Simulate scroll right
                else:
                    self.logger.error(f"Scroll action direction '{direction}' not supported or missing value: {value}")
                    raise ValueError("Invalid Scroll action parameters.") 
            else:
                self.logger.error(f"Scroll action requires dict 'value', got: {value}")
                raise ValueError("Scroll action 'value' must be a dictionary.")
        
        elif action_type == "Wait":
            if isinstance(value, (int, float)) and value > 0:
                await asyncio.sleep(value / 1000.0) # Value is in milliseconds
            else:
                self.logger.error(f"Wait action requires positive number 'value' (ms), got: {value}")
                raise ValueError("Wait action 'value' (ms) must be a positive number.")

        elif action_type == "Screenshot":
            screenshot_b64 = await self.agent.take_screenshot()
            self.logger.info(f"Screenshot taken. Length: {len(screenshot_b64)} chars. (Not saving to file here)")
            # In a real scenario, you might save this or pass it to the LLM if needed.

        elif action_type == "ExtractInfo":
            # This would require more complex logic: 
            # 1. Locate element by element_id from current_context
            # 2. Extract attributes specified in value.get("attributes_to_extract")
            # 3. Return this info, likely by updating a shared state or logging it.
            self.logger.warning(f"ExtractInfo action for element '{element_id}' with value '{value}' is not fully implemented.")
            # Placeholder: log what would be extracted
            if element_id and isinstance(value, dict) and "attributes_to_extract" in value:
                self.logger.info(f"Would attempt to extract attributes {value['attributes_to_extract']} from element '{element_id}'")
            else:
                 raise ValueError("ExtractInfo action requires element_id and value with attributes_to_extract")

        else:
            self.logger.error(f"Action type '{action_type}' execution not implemented.")
            raise NotImplementedError(f"Execution for action type '{action_type}' not implemented.")
        
        await asyncio.sleep(0.3) # Slightly longer default delay after action

    async def action(self, user_instruction: str, action_context_str: Optional[str] = None) -> Dict[str, Any]:
        self.logger.info(f"PageTaskExecutor.action: User instruction = '{user_instruction}'")
        current_log_for_replan: Optional[str] = None # For multi-step planning, not used in this simplified version
        replan_count = 0
        max_replans = 1 # For now, only one planning attempt, no re-planning loop.
        
        all_actions_executed_for_instruction: List[PlanningAction] = []
        final_reasoning: Optional[str] = None

        while replan_count < max_replans:
            replan_count += 1
            self.logger.info(f"Planning iteration {replan_count} for: '{user_instruction}'")
            
            # Get UI Context (ensure it's the new AIWebUIContext format)
            # This is a critical point: get_ui_context must return the AIWebUIContext compatible type
            current_ui_context_dict = await self.agent.get_ui_context(action="plan")
            
            # Ensure current_ui_context_dict matches WebUIContext structure expected by PythonInsight
            # This might involve a transformation if get_ui_context returns OriginalWebUIContext
            # For now, assume get_ui_context is updated or PythonInsight handles it.
            # The type hint for current_ui_context_dict should be WebUIContext (the AI one)
            current_ui_context: WebUIContext = current_ui_context_dict # type: ignore
            
            plan_response = await self.insight.plan(
                user_instruction,
                context=current_ui_context, # Pass the AI-compatible context
                log=current_log_for_replan,
                action_context=action_context_str,
                page_type=self.agent.page_type # type: ignore
            )
            
            # The new PlanResponse doesn't have "error", "log", "more_actions_needed_by_instruction", "yamlFlow"
            # It has "actions" and "reasoning"
            actions_to_execute = plan_response.get("actions", [])
            final_reasoning = plan_response.get("reasoning", "No overall reasoning provided.")

            if not actions_to_execute:
                self.logger.info(f"No actions from planning for instruction: '{user_instruction}'. Reasoning: {final_reasoning}")
                break 

            for planned_action in actions_to_execute:
                self.logger.info(f"Executing planned_action: {planned_action}")
                try:
                    await self._execute_plan_action(planned_action, current_ui_context)
                    all_actions_executed_for_instruction.append(planned_action)
                except Exception as e:
                    self.logger.error(f"Error executing action {planned_action.get('type', 'Unknown')}: {e}", exc_info=True)
                    # If one action fails, we might stop the whole sequence for this plan
                    # Or, an LLM could re-plan based on the error.
                    # For now, re-raise to stop execution of this plan.
                    raise 
            
            # Since more_actions_needed_by_instruction is removed, we assume one plan is enough for now.
            self.logger.info(f"Finished executing actions for instruction: '{user_instruction}'")
            break

        # The return structure might need adjustment based on what ai_action in AgentOverChromeBridge expects.
        # Previous return was: {"status": "success", "detail": "...", "yamlFlow": ...}
        # New simple return:
        return {
            "status": "success" if all_actions_executed_for_instruction else "no_actions",
            "detail": f"Executed {len(all_actions_executed_for_instruction)} actions. Overall reasoning: {final_reasoning}",
            "executed_actions": all_actions_executed_for_instruction
        }

    async def assert_task(self, assertion_prompt: str) -> Dict[str, Any]:
        self.logger.info(f"PageTaskExecutor.assert_task: Assertion = '{assertion_prompt}'")
        current_ui_context_dict = await self.agent.get_ui_context(action="assert")
        current_ui_context: WebUIContext = current_ui_context_dict # type: ignore

        result: InsightAssertionResponse = await self.insight.assert_method(assertion_prompt, context=current_ui_context)
        
        if not result.get("passed", False):
            error_msg = result.get("reason", f"Assertion failed: {assertion_prompt}")
            self.logger.error(error_msg)
            raise AssertionError(error_msg)
        
        self.logger.info(f"Assertion '{assertion_prompt}' passed. Reason: {result.get('reason')}")
        # Return structure should align with ai_assert in AgentOverChromeBridge expectations
        # The InsightAssertionResponse is {"passed": bool, "reason": str}
        return {"pass": result.get("passed"), "thought": result.get("reason")}

class AgentOverChromeBridge:
    """
    通过Chrome扩展桥接与浏览器页面交互的代理。
    这个Python类现在将启动一个Socket.IO服务器，等待Chrome扩展连接。
    """

    def __init__(
        self,
        port: int = DefaultBridgeServerPort,
        on_browser_connect: Optional[Callable[[], None]] = None, # 当浏览器连接时回调
        on_browser_disconnect: Optional[Callable[[str], None]] = None, # 当浏览器断开时回调
        # 从 demo_bing_search.py 中移除的参数，但保留定义以防未来使用
        close_conflict_server: bool = False, 
        server_listening_timeout: int = 20000 
    ):
        self.port = port
        self._server_task: Optional[asyncio.Task] = None
        self._server_running = asyncio.Event() # 用于等待服务器实际启动
        self._uvicorn_server: Optional[uvicorn.Server] = None

        # 创建BridgeServer实例
        self._bridge_server = BridgeServer(
            port=self.port,
            on_connect=self._handle_browser_connect, # 内部处理函数
            on_disconnect=self._handle_browser_disconnect # 内部处理函数
        )
        
        self._user_on_browser_connect = on_browser_connect
        self._user_on_browser_disconnect = on_browser_disconnect
        
        self.connected = False # 指示浏览器是否已连接到我们的服务器
        
        # 新增: 初始化 page_type, insight 和 task_executor
        self.page_type = "chrome-extension-proxy" 
        self.insight = PythonInsight(self)
        self.task_executor = PageTaskExecutor(self, self.insight)
        # logger 已在模块级别定义，这里可以直接使用 logger.info 等

    def _handle_browser_connect(self):
        logger.info("Browser client connected to Python BridgeServer.")
        self.connected = True
        if self._user_on_browser_connect:
            self._user_on_browser_connect()

    def _handle_browser_disconnect(self, reason: str):
        logger.info(f"Browser client disconnected from Python BridgeServer. Reason: {reason}")
        self.connected = False
        if self._user_on_browser_disconnect:
            self._user_on_browser_disconnect(reason)

    async def start(self):
        """启动Socket.IO服务器并等待浏览器连接。"""
        if self._server_task and not self._server_task.done():
            logger.warning("Server is already running or starting.")
            return

        logger.info(f"Python BridgeServer正在端口 {self.port} 启动...")
        
        config = uvicorn.Config(
            self._bridge_server.app, 
            host="127.0.0.1", 
            port=self.port, 
            log_level="warning" # uvicorn自身的日志级别，可以调整
        )
        self._uvicorn_server = uvicorn.Server(config)

        # 在一个任务中运行Uvicorn服务器，这样start可以是非阻塞的
        # 或者，如果希望start阻塞直到服务器停止，可以直接await self._uvicorn_server.serve()
        # 这里我们选择非阻塞启动，并用事件来同步
        
        async def serve():
            try:
                self._server_running.set() # 通知服务器已配置并即将启动
                await self._uvicorn_server.serve()
                logger.info("Python BridgeServer已停止.")
            except Exception as e:
                logger.error(f"Python BridgeServer 运行错误: {e}", exc_info=True)
            finally:
                self._server_running.clear()
                self.connected = False # 确保服务器停止后连接状态为False

        self._server_task = asyncio.create_task(serve())
        # 可以选择等待服务器真正开始监听，但这对于uvicorn有点复杂
        # uvicorn.Server.serve() 本身会阻塞直到服务器停止
        # 我们通过 self._server_running.wait() 来确保 serve() 至少已经开始执行
        await self._server_running.wait() 
        logger.info(f"Python BridgeServer应该已在 http://127.0.0.1:{self.port} 上运行")

    async def close(self):
        """关闭Socket.IO服务器。"""
        logger.info("正在关闭Python BridgeServer...")
        await self._bridge_server.close() # 首先尝试关闭BridgeServer内部逻辑（例如断开客户端）
        
        if self._uvicorn_server:
            # Uvicorn 服务器的优雅关闭
            self._uvicorn_server.should_exit = True 

        if self._server_task:
            if not self._server_task.done():
                try:
                    # 等待服务器任务完成 (Uvicorn停止)
                    await asyncio.wait_for(self._server_task, timeout=5.0) 
                except asyncio.TimeoutError:
                    logger.warning("关闭服务器任务超时，可能需要手动停止进程。")
                    self._server_task.cancel() # 如果超时则尝试取消
                except Exception as e:
                    logger.error(f"关闭服务器任务时发生错误: {e}")
            self._server_task = None
        
        self.connected = False
        logger.info("Python BridgeServer已关闭。")

    async def call(
        self, 
        method: str, 
        args: Optional[list] = None, # args 现在是 Optional
        timeout: int = BridgeCallTimeout
    ) -> Any:
        """在连接的Chrome浏览器中执行方法。"""
        if not self.connected:
            # 在TS版本中，如果未连接，call会尝试连接。
            # 在这个服务器模式下，我们需要浏览器主动连接到我们。
            # 所以如果Python服务器已启动但浏览器未连接，则调用应该失败。
            raise ConnectionError(
                "无法执行调用：Chrome浏览器未连接到Python BridgeServer。请确保浏览器扩展已启用并处于Bridge模式。"
            )
        
        # 使用BridgeServer的call_on_browser方法
        return await self._bridge_server.call_on_browser(method, args if args is not None else [], timeout)

    # 新增: get_ui_context 方法
    async def get_ui_context(self, action: Optional[str] = None) -> WebUIContext:
        logger.info(f"Getting UI Context (for action: {action})...")
        
        # 辅助函数将原始JS端节点转换为 WebElementInfo
        def _convert_raw_node_to_web_element_info(raw_node_data: Dict[str, Any]) -> WebElementInfo:
            # 从 raw_node_data 中提取字段，并映射到 WebElementInfo
            # 这部分依赖于 window.midscene_element_inspector.webExtractNodeTree() 返回的具体结构
            # 假设 raw_node_data 有 id, attributes, content/description 等字段
            
            element_id = str(raw_node_data.get('id', raw_node_data.get('element_id', 'unknown_id')))
            
            # 生成描述：尝试从多个字段获取，如 aria-label, name, placeholder, role, textContent
            desc_parts = []
            if raw_node_data.get('attributes') and isinstance(raw_node_data['attributes'], dict):
                if raw_node_data['attributes'].get('aria-label'):
                    desc_parts.append(f"Label: {raw_node_data['attributes']['aria-label']}")
                if raw_node_data['attributes'].get('name'):
                    desc_parts.append(f"Name: {raw_node_data['attributes']['name']}")
                if raw_node_data['attributes'].get('placeholder'):
                    desc_parts.append(f"Placeholder: {raw_node_data['attributes']['placeholder']}")
                role = raw_node_data['attributes'].get('role')
                if role:
                    desc_parts.append(f"Role: {role}")
                # value 可能是 input 的当前值
                value_attr = raw_node_data['attributes'].get('value')
                if value_attr:
                     desc_parts.append(f"Value: '{str(value_attr)[:30]}'" + ("..." if len(str(value_attr)) > 30 else ""))

            # 尝试获取文本内容 (textContent, innerText, or a specific description field)
            text_content = raw_node_data.get('content', 
                                         raw_node_data.get('textContent', 
                                         raw_node_data.get('innerText', 
                                         raw_node_data.get('description'))))
            if text_content and isinstance(text_content, str) and text_content.strip():
                desc_parts.append(f"Text: '{text_content.strip()[:50]}'" + ("..." if len(text_content.strip()) > 50 else ""))
            
            description = ", ".join(desc_parts) if desc_parts else f"Element (id: {element_id})"
            if not description and raw_node_data.get('tagName'): # fallback to tagname
                description = f"Tag: {raw_node_data['tagName']}"
            if not description: # last fallback
                description = "Generic element"

            # 转换 attributes 字典，确保所有值都是字符串
            raw_attrs = raw_node_data.get('attributes', {})
            attributes = {str(k): str(v) for k, v in raw_attrs.items()} if isinstance(raw_attrs, dict) else {}
            
            # 获取元素的矩形信息
            rect = raw_node_data.get('rect', {})
            if not isinstance(rect, dict):
                rect = {'x': 0, 'y': 0, 'width': 0, 'height': 0}
            
            # 计算中心点
            center = (
                rect.get('x', 0) + rect.get('width', 0) // 2,
                rect.get('y', 0) + rect.get('height', 0) // 2
            )
            
            # 获取定位器信息
            locator = raw_node_data.get('locator')
            
            # 获取索引ID
            index_id = raw_node_data.get('indexId', 0)
            
            # 获取内容
            content = text_content or description
            
            return WebElementInfo(
                id=element_id,
                rect=rect,
                center=center,
                content=str(content or ""),
                attributes=attributes,
                locator=locator,
                indexId=index_id
            )

        # 辅助递归函数将原始JS端树转换为 ElementTreeNode
        def _convert_raw_tree_to_element_tree(raw_node: Dict[str, Any]) -> Optional[ElementTreeNode]:
            if not raw_node: # Handle cases where a node might be null or empty
                return None

            # 'node' field in OriginalElementTreeNode or the root itself could be the element data
            current_node_data = raw_node.get('node') or raw_node 
            if not current_node_data or not isinstance(current_node_data, dict):
                 # If current_node_data is not a dict (e.g. it is None or a list where a dict was expected)
                 # this branch of the tree cannot be processed according to ElementTreeNode structure.
                 # Log a warning or error if this happens unexpectedly.
                 logger.warning(f"Skipping node in tree conversion, expected dict, got {type(current_node_data)}: {str(current_node_data)[:100]}")
                 return None
            
            web_element_info = _convert_raw_node_to_web_element_info(current_node_data)
            
            children = []
            raw_children_data = raw_node.get('children', [])
            if isinstance(raw_children_data, list):
                for raw_child_node in raw_children_data:
                    if isinstance(raw_child_node, dict):
                        converted_child = _convert_raw_tree_to_element_tree(raw_child_node)
                        if converted_child:
                            children.append(converted_child)
                    else:
                        logger.warning(f"Child node in tree is not a dict, skipping: {type(raw_child_node)}")
            
            return ElementTreeNode(node=web_element_info, children=children)

        try:
            url_task = self.get_url()
            title_task = self.get_title()
            screenshot_task = self.take_screenshot()
            size_task = self.size()
            
            # Get structured element tree from the browser extension
            # This script should be provided by midscene_element_inspector on the page
            tree_script = "(typeof window.midscene_element_inspector !== 'undefined' && typeof window.midscene_element_inspector.webExtractNodeTree === 'function') ? JSON.stringify(window.midscene_element_inspector.webExtractNodeTree()) : null;"
            raw_tree_json_str_task = self.evaluate(tree_script)

            # Get focused element ID (if possible from the extension)
            focused_element_script = "(typeof window.midscene_element_inspector !== 'undefined' && typeof window.midscene_element_inspector.getFocusedElementId === 'function') ? window.midscene_element_inspector.getFocusedElementId() : null;"
            focused_id_task = self.evaluate(focused_element_script)

            url, title, screenshot_base64, size_data, raw_tree_json_str, focused_element_id_raw = await asyncio.gather(
                url_task, title_task, screenshot_task, size_task, raw_tree_json_str_task, focused_id_task
            )
            
            # 处理元素树
            element_tree: Optional[ElementTreeNode] = None
            content_list: List[WebElementInfo] = []
            
            if raw_tree_json_str and isinstance(raw_tree_json_str, str):
                try:
                    raw_tree_root_dict = json.loads(raw_tree_json_str)
                    if isinstance(raw_tree_root_dict, dict):
                        element_tree = _convert_raw_tree_to_element_tree(raw_tree_root_dict)
                        # 从树中提取扁平的元素列表
                        def extract_elements(node: Optional[ElementTreeNode]) -> List[WebElementInfo]:
                            if not node:
                                return []
                            result = []
                            if node.get('node'):
                                result.append(node['node'])
                            for child in node.get('children', []):
                                result.extend(extract_elements(child))
                            return result
                        content_list = extract_elements(element_tree)
                    else:
                        logger.error(f"Parsed element tree JSON is not a dict: {type(raw_tree_root_dict)}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse element tree JSON string: {e}. String: {raw_tree_json_str[:200]}...")
            elif isinstance(raw_tree_json_str, dict): # If evaluate already parsed it (less likely for stringify)
                element_tree = _convert_raw_tree_to_element_tree(raw_tree_json_str)
                content_list = extract_elements(element_tree)
            else:
                logger.warning(f"midscene_element_inspector.webExtractNodeTree() returned no data or unexpected type: {type(raw_tree_json_str)}. Inspector might not be available or active.")

            focused_element_id_str: Optional[str] = None
            if focused_element_id_raw and isinstance(focused_element_id_raw, str):
                focused_element_id_str = focused_element_id_raw
            
            # Task guidance - for now, an empty list. This could be populated from prior interactions or a task queue.
            task_guidance: List[str] = [] 

            ui_context: WebUIContext = {
                "content": content_list,
                "tree": element_tree or ElementTreeNode(node=None, children=[]),
                "size": size_data,
                "screenshotBase64": screenshot_base64,
                "url": url or "",
                "title": title
            }
            
            logger.info("UI Context retrieved successfully.")
            return ui_context
            
        except Exception as e:
            logger.error(f"Error getting UI context: {e}", exc_info=True)
            return WebUIContext(
                content=[],
                tree=ElementTreeNode(node=None, children=[]),
                size={"width": 0, "height": 0, "dpr": 1.0},
                screenshotBase64="",
                url="",
                title="Error retrieving context"
            )

    # 新增: size 方法
    async def size(self) -> Dict[str, Union[int, float]]:
        js_expr = "JSON.stringify({width: document.documentElement.clientWidth, height: document.documentElement.clientHeight, dpr: window.devicePixelRatio})"
        size_str = await self.evaluate(js_expr) # evaluate应能处理执行结果
        try:
            # 确保 evaluate 返回的是可被 json.loads 解析的字符串，或者直接是字典
            if isinstance(size_str, dict): # 如果 evaluate 已经解析了
                 size_data = size_str
            elif isinstance(size_str, str):
                 size_data = json.loads(size_str)
            else:
                raise TypeError(f"Unexpected type from self.evaluate for size: {type(size_str)}")

            if isinstance(size_data, dict) and "width" in size_data and "height" in size_data and "dpr" in size_data:
                return size_data
            else:
                logger.error(f"Parsed size data is not in expected format: {size_data}")
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to get or parse page size: {e}. Raw response: '{size_str}'")
        return {"width": 0, "height": 0, "dpr": 1.0} 

    # 页面操作方法 (get_url, get_title, navigate, version, take_screenshot, get_content, evaluate) 保持不变
    # (此处省略这些方法的实现，确保它们与之前的版本一致)
    async def get_url(self, timeout: int = BridgeCallTimeout) -> str:
        return await self.call("url", timeout=timeout)

    async def get_title(self, timeout: int = BridgeCallTimeout) -> str:
        # evaluateJavaScript returns a more complex object
        response = await self.call("evaluateJavaScript", ["document.title"], timeout=timeout)
        if response and isinstance(response, dict) and "result" in response and isinstance(response["result"], dict):
            return response["result"].get("value", "")
        logger.warning(f"Could not parse title from response: {response}")
        return ""

    async def navigate(self, url: str, timeout: int = BridgeCallTimeout):
        js_code = f"window.location.href = '{url}';"
        # navigate doesn't typically return a meaningful value from evaluateJavaScript
        await self.call("evaluateJavaScript", [js_code], timeout=timeout)

    async def version(self, timeout: int = BridgeCallTimeout) -> str:
        # __VERSION__ is declared in the extension's context
        # This assumes evaluateJavaScript can access it.
        response = await self.call("evaluateJavaScript", ["__VERSION__"], timeout=timeout)
        if response and isinstance(response, dict) and "result" in response and isinstance(response["result"], dict):
            return response["result"].get("value", "unknown")
        logger.warning(f"Could not parse version from response: {response}")
        return "unknown"

    async def take_screenshot(self, timeout: int = BridgeCallTimeout) -> str:
        """获取页面截图（返回base64编码的图片数据）"""
        # screenshotBase64 is expected to return the base64 string directly
        return await self.call("screenshotBase64", timeout=timeout)

    async def get_content(self, timeout: int = BridgeCallTimeout) -> str:
        """获取页面HTML内容"""
        response = await self.call("evaluateJavaScript", ["document.documentElement.outerHTML"], timeout=timeout)
        if response and isinstance(response, dict) and "result" in response and isinstance(response["result"], dict):
            return response["result"].get("value", "")
        logger.warning(f"Could not parse content from response: {response}")
        return ""

    async def evaluate(self, js_code: str, timeout: int = BridgeCallTimeout) -> Any:
        """在页面上下文中执行JavaScript代码"""
        # The raw response from evaluateJavaScript might be complex.
        # For a generic evaluate, returning the somewhat raw "result" part might be best,
        # or the user might expect the direct "value" if simple.
        # Let's try to return result.value if available, else the result object.
        response = await self.call("evaluateJavaScript", [js_code], timeout=timeout)
        if response and isinstance(response, dict) and "result" in response:
            if isinstance(response["result"], dict) and "value" in response["result"]:
                return response["result"]["value"]
            return response["result"] # Return the content of "result" if "value" is not present
        logger.warning(f"Could not parse evaluate from response: {response}")
        return None

    async def connect_new_tab_with_url(self, url: str, timeout: int = BridgeCallTimeout) -> bool:
        """指示Chrome扩展打开一个新标签页并导航到指定URL，并将其与当前桥接会话关联。"""
        success = False
        try:
            logger.info(f"尝试调用 connectNewTabWithUrl, URL: {url}")
            await self.call(BridgeEvent.ConnectNewTabWithUrl, [url], timeout=timeout)
            logger.info(f"命令 connectNewTabWithUrl 已发送。")
            await asyncio.sleep(3)
            success = True
        except Exception as e:
            logger.error(f"调用 connectNewTabWithUrl 失败: {e}", exc_info=False)

        if not success:
            logger.warning(f"connect_new_tab_with_url: 无法通过 connectNewTabWithUrl 初始化新标签页: {url}。后续页面操作可能因此失败。")
        
        return success

    # 重构: AI 方法现在使用 self.task_executor
    async def ai_action(self, task_prompt: str, action_context: Optional[str] = None) -> dict:
        logger.info(f"AgentOverChromeBridge.ai_action: Task = '{task_prompt}'")
        return await self.task_executor.action(user_instruction=task_prompt, action_context_str=action_context)

    async def ai_assert(self, assertion: str, msg: Optional[str] = None, opt: Optional[dict] = None) -> dict:
        logger.info(f"AgentOverChromeBridge.ai_assert: Assertion = '{assertion}'")
        # msg 和 opt 当前未被 task_executor.assert_task 使用，但保留API一致性
        return await self.task_executor.assert_task(assertion_prompt=assertion)

    # 其他 AI 方法 (ai, ai_tap, etc.) 保持 NotImplementedError 或根据需要实现
    async def ai(self, task_prompt: str, task_type: str = 'action') -> Any:
        logger.info(f"AgentOverChromeBridge.ai: Task Type='{task_type}', Prompt='{task_prompt}'")
        if task_type == 'action':
            return await self.ai_action(task_prompt)
        elif task_type == 'assert':
            return await self.ai_assert(task_prompt)
        else:
            logger.error(f"AI task_type '{task_type}' not supported by generic 'ai' method.")
            raise NotImplementedError(f"AI task_type '{task_type}' not implemented in 'ai' method.")

    async def ai_tap(self, locate_prompt: str, opt: Optional[dict] = None) -> Any:
        logger.warning(f"ai_tap for '{locate_prompt}' called but not implemented.")
        raise NotImplementedError("ai_tap is not implemented yet. Requires full AI planning and execution.")

    async def ai_hover(self, locate_prompt: str, opt: Optional[dict] = None) -> Any:
        logger.warning(f"ai_hover for '{locate_prompt}' called but not implemented.")
        raise NotImplementedError("ai_hover is not implemented yet.")

    async def ai_input(self, value: str, locate_prompt: str, opt: Optional[dict] = None) -> Any:
        logger.warning(f"ai_input for '{locate_prompt}' with value '{value}' called but not implemented.")
        raise NotImplementedError("ai_input is not implemented yet.")

    async def ai_keyboard_press(self, key_name: str, locate_prompt: Optional[str] = None, opt: Optional[dict] = None) -> Any:
        # 如果只是简单地转发，可以这样做：
        # self.logger.info(f"AI Keyboard Press: key='{key_name}', locate_prompt='{locate_prompt}'")
        # if locate_prompt:
        #     raise NotImplementedError("ai_keyboard_press with locate_prompt requires element focusing logic.")
        # return await self.keyboard_press(key_name)
        # 但更完整的 PageAgent.aiKeyboardPress 包含构建计划和执行的逻辑，此处暂不实现
        logger.warning(f"ai_keyboard_press for key '{key_name}' called but not fully implemented according to PageAgent structure.")
        raise NotImplementedError("ai_keyboard_press is not fully implemented yet (plan building missing).")

    async def ai_scroll(self, scroll_param: dict, locate_prompt: Optional[str] = None, opt: Optional[dict] = None) -> Any:
        logger.warning(f"ai_scroll with params '{scroll_param}' for '{locate_prompt}' called but not implemented.")
        raise NotImplementedError("ai_scroll is not implemented yet.")

    async def ai_query(self, demand: Any) -> Any:
        logger.warning(f"ai_query with demand '{demand}' called but not implemented.")
        raise NotImplementedError("ai_query is not implemented yet.")

    async def ai_boolean(self, prompt: str) -> bool:
        logger.warning(f"ai_boolean for '{prompt}' called but not implemented.")
        raise NotImplementedError("ai_boolean is not implemented yet.")

    async def ai_number(self, prompt: str) -> Union[int, float]:
        logger.warning(f"ai_number for '{prompt}' called but not implemented.")
        raise NotImplementedError("ai_number is not implemented yet.")

    async def ai_string(self, prompt: str) -> str:
        logger.warning(f"ai_string for '{prompt}' called but not implemented.")
        raise NotImplementedError("ai_string is not implemented yet.")

    async def ai_locate(self, prompt: str, opt: Optional[dict] = None) -> Any:
        logger.warning(f"ai_locate for '{prompt}' called but not implemented.")
        raise NotImplementedError("ai_locate is not implemented yet.")

    async def ai_wait_for(self, assertion: str, opt: Optional[dict] = None) -> Any:
        logger.warning(f"ai_wait_for for '{assertion}' called but not implemented.")
        raise NotImplementedError("ai_wait_for is not implemented yet.")

    # Keyboard primitives (ensure these are correctly defined and used by ai_action)
    async def _keyboard_action(self, event_suffix: str, *args: Any) -> Any:
        # Forwarding call to the bridge server
        # 使用 call_on_browser 方法替代 call
        return await self._bridge_server.call_on_browser(f"keyboard.{event_suffix}", list(args))

    async def keyboard_type(self, text_to_type: str) -> Any:
        logger.debug(f"Keyboard type: '{text_to_type}'")
        return await self._keyboard_action("type", text_to_type)

    async def keyboard_press(self, key_name_or_action: Union[str, dict, list[dict]]) -> Any:
        logger.debug(f"Keyboard press: {key_name_or_action}")
        if isinstance(key_name_or_action, str):
            action_payload = {"key": key_name_or_action}
        elif isinstance(key_name_or_action, dict): # e.g. {"key": "a", "command": "selectAll"}
            action_payload = key_name_or_action
        elif isinstance(key_name_or_action, list): # e.g. [{"key": "Control"}, {"key": "a"}]
            action_payload = key_name_or_action
        else:
            logger.error(f"Unsupported type for keyboard_press action: {type(key_name_or_action)}")
            raise ValueError(f"Unsupported type for keyboard_press action: {type(key_name_or_action)}")
        return await self._keyboard_action("press", action_payload)

    # Mouse primitives (ensure these exist and are used by future AI plan executions)
    async def _mouse_action(self, event_suffix: str, *args: Any) -> Any:
        # 使用 call_on_browser 方法替代 call
        return await self._bridge_server.call_on_browser(f"mouse.{event_suffix}", list(args))

    async def mouse_click(self, x: int, y: int, button: str = "left", click_count: int = 1) -> Any:
        logger.debug(f"Mouse click at ({x}, {y}), button: {button}, count: {click_count}")
        return await self._mouse_action("click", x, y)

    async def mouse_wheel(self, delta_x: int, delta_y: int, start_x: Optional[int] = None, start_y: Optional[int] = None) -> Any:
        logger.debug(f"Mouse wheel: dX={delta_x}, dY={delta_y}, start=({start_x},{start_y})")
        args = [delta_x, delta_y]
        if start_x is not None:
            args.append(start_x)
        if start_y is not None:
            args.append(start_y)
        return await self._mouse_action("wheel", *args)

    async def mouse_move(self, x: int, y: int) -> Any:
        logger.debug(f"Mouse move to ({x}, {y})")
        return await self._mouse_action("move", x, y)

    async def mouse_drag(self, from_pos: dict, to_pos: dict) -> Any: # from_pos: {"x":0,"y":0}
        logger.debug(f"Mouse drag from {from_pos} to {to_pos}")
        return await self._mouse_action("drag", from_pos, to_pos)

    # 注意：旧的 PageCliSide 和 BridgeClient 不再直接由此类使用。
    # 这个类现在是服务器端。