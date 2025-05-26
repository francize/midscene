# midscene_python_bridge/bridge_mode/ai_tools.py
import logging
from typing import List, Dict, Any, Optional, Literal, TypedDict
import datetime
import json

from .types import (
    WebElementInfo,
    ElementTreeNode,
    WebUIContext,
    PlanningAction,
    PlanResponse,
    InsightAssertionResponse
)

logger = logging.getLogger("AITools")

# Placeholder for PageType, equivalent to TypeScript's PageType
# For now, we'll just use string, but this could be an Enum or a more complex type later.
PageType = str # e.g., "chrome-extension-proxy", "playwright", "puppeteer"

# Assuming these types are defined in a shared location or agent_cli_side.py
# If not, they should be defined here or imported.
# For now, let's redefine for clarity within this module if they are not easily importable.

class WebElementInfo(TypedDict):
    attributes: dict[str, str]
    description: str
    element_id: str

class ElementTreeNode(TypedDict):
    node: Optional[WebElementInfo]
    children: List['ElementTreeNode']

class WebUIContext(TypedDict):
    url: str
    title: str
    task_guidance: List[str]
    tree: Optional[ElementTreeNode]
    focused_element_id: Optional[Optional[str]]
    content: List[WebElementInfo]
    size: Dict[str, Any]
    screenshotBase64: str

class PlanningAction(TypedDict):
    type: Literal["Input", "KeyboardPress", "Tap", "Scroll", "Navigate", "Wait", "ExtractInfo", "Screenshot"]
    value: Optional[str | dict[str, Any]]
    element_id: Optional[str]
    reasoning: Optional[str]

class PlanResponse(TypedDict):
    actions: List[PlanningAction]
    reasoning: Optional[str]

class InsightAssertionResponse(TypedDict):
    passed: bool
    reason: str

def get_time_zone_info() -> str:
    """Returns the current time zone information."""
    try:
        # This will get the local time zone name (e.g., 'America/New_York', 'UTC')
        # python 3.9+
        return datetime.datetime.now(datetime.timezone.utc).astimezone().tzname() or "Unknown"
    except Exception:
        return "UTC" # Fallback

def get_language() -> str:
    """Returns the system's preferred language (simplified)."""
    # In a real scenario, this might involve more complex detection
    # or be a configurable setting.
    return "en-US"

def _build_common_action_description() -> str:
    """Describes the available actions to the LLM."""
    actions_description = """
Available actions:
1.  **Navigate**: Go to a specific URL.
    - `{"type": "Navigate", "value": "URL"}` (e.g., `{"type": "Navigate", "value": "https://www.google.com"}`)
2.  **Input**: Type text into an input field.
    - `{"type": "Input", "element_id": "element_id_of_input_field", "value": "text to type"}`
3.  **Tap**: Click or tap on an element.
    - `{"type": "Tap", "element_id": "element_id_of_element_to_tap"}`
4.  **KeyboardPress**: Press a key on the keyboard (e.g., Enter, Tab, Escape).
    - `{"type": "KeyboardPress", "value": "KeyName"}` (e.g., `{"type": "KeyboardPress", "value": "Enter"}`)
5.  **Scroll**: Scroll the page or a specific scrollable element.
    - `{"type": "Scroll", "value": {"direction": "down|up|left|right", "amount": "small|large"}}` (for page scroll)
    - `{"type": "Scroll", "element_id": "element_id_of_scrollable_area", "value": {"direction": "down|up|left|right", "amount": "small|large"}}` (for element scroll)
6.  **Wait**: Pause execution for a specified duration.
    - `{"type": "Wait", "value": milliseconds}` (e.g., `{"type": "Wait", "value": 500}`)
7.  **ExtractInfo**: Extract information from an element.
    - `{"type": "ExtractInfo", "element_id": "element_id_to_extract_from", "value": {"attributes_to_extract": ["attribute_name"]}}` (e.g. `value`, `text_content`, `href`)
8.  **Screenshot**: Take a screenshot of the current view.
    - `{"type": "Screenshot"}`

Provide your response as a JSON object conforming to the PlanResponse schema:
`{"actions": [{"type": "ActionType", ...}], "reasoning": "Your thought process"}`
Each action in the 'actions' list must be one of the available actions described above.
Ensure 'element_id' corresponds to an ID from the provided UI context if the action requires it.
Focus on the immediate next step(s) to accomplish the user's task.
    """
    return actions_description

def _element_to_string(element_node: ElementTreeNode, indent: str = "") -> str:
    """Converts an element tree node to a string representation for the LLM."""
    element_info = element_node.get('node') # Use .get() to safely access 'node'
    if not element_info:
        return f"{indent}- [Empty Node]\n" # Return if no element info

    # Basic attributes, could be expanded. Avoid overly verbose like full style.
    attrs_str = ", ".join(f'{k}="{v}"' for k, v in element_info.get('attributes', {}).items() if k in ['role', 'aria-label', 'name', 'placeholder', 'value', 'type', 'href', 'data-test-id'])
    
    description = element_info.get('description', 'No description')
    # Sanitize description to remove potential JSON breaking characters if not already clean
    description = description.replace('"', "'")

    # Include text content if available and relevant, e.g., from description or specific attributes
    text_content_parts = []
    if element_info.get('attributes', {}).get('value'):
        text_content_parts.append(f"value: \"{element_info['attributes']['value']}\"")
    if element_info.get('attributes', {}).get('placeholder'):
         text_content_parts.append(f"placeholder: \"{element_info['attributes']['placeholder']}\"")

    text_content_str = ""
    if text_content_parts:
        text_content_str = f" ({', '.join(text_content_parts)})"

    output = f'{indent}- Element ID: "{element_info.get("element_id", "N/A")}", Description: "{description}"{text_content_str}' # Use .get for element_id
    if attrs_str:
        output += f', Attributes: [{attrs_str}]'
    output += "\n"
    
    children = element_node.get('children', [])
    if children:
        for child_node in children:
            # Check if child_node itself and its 'node' are not None before recursive call
            if child_node and child_node.get('node'):
                 output += _element_to_string(child_node, indent + "  ")
            elif child_node: # If child_node exists but its 'node' is None
                 output += f'{indent}  - [Empty Child Node]\n'
            # If child_node is None, it's skipped by the loop structure or .get('children', [])
    return output

def describe_ui_context_for_llm(ui_context: WebUIContext) -> str:
    """Formats the WebUIContext into a string representation suitable for an LLM prompt."""
    description = f"Current URL: {ui_context['url']}\\n"
    description += f"Page Title: {ui_context['title']}\\n"
    
    if ui_context.get('focused_element_id'):
        description += f"Focused Element ID: {ui_context['focused_element_id']}\\n"

    if ui_context.get('task_guidance'):
        description += "Task Guidance (previous steps or context):\\n"
        for guidance in ui_context['task_guidance']:
            description += f"- {guidance}\\n"
    
    description += "\\nInteractive Elements Tree:\\n"
    if ui_context['tree']:
        description += _element_to_string(ui_context['tree'])
    else:
        description += "No interactive elements detected or provided.\\n"
        
    return description

def build_planning_system_prompt_messages() -> List[dict[str, str]]:
    """Builds the system prompt messages for the planning LLM call."""
    
    time_zone = get_time_zone_info()
    language = get_language()
    action_description = _build_common_action_description()

    system_prompt = f"""
You are an expert AI assistant tasked with controlling a web browser to achieve a user's goal.
Your capabilities include navigating, clicking, typing, scrolling, and extracting information from web pages.
Current Time Zone: {time_zone}
Language: {language}

You will be given:
1.  The user's overall task.
2.  The current state of the web page (URL, title, and a tree of interactive elements with their IDs and descriptions).
3.  Optionally, any guidance or context from previous steps.

Your goal is to determine the next best action(s) to take to move closer to completing the user's task.
Think step-by-step. Analyze the UI context and the task carefully.

{action_description}

Choose the most appropriate action(s) from the list. If multiple actions are needed sequentially for the immediate next step, you can provide them.
Be precise with element IDs if an action targets a specific element.
If an element is not clearly identifiable or if you need to scroll to find an element, indicate that in your reasoning or use a scroll action.
If the task is ambiguous or requires information not present, you can state that in your reasoning.
Output your response strictly as a JSON object conforming to the PlanResponse schema. Do not add any text before or after the JSON object.
Example of a valid JSON response:
`{{"actions": [{{"type": "Input", "element_id": "search_box_123", "value": "hello world", "reasoning": "The user wants to search, so I will type into the search box."}}], "reasoning": "Identified search box and will type the query."}}`
Another example:
`{{"actions": [{{"type": "Tap", "element_id": "submit_button_456", "reasoning": "After typing, I need to click the submit button."}}], "reasoning": "The next step is to submit the form."}}`
    """
    return [{"role": "system", "content": system_prompt.strip()}]

def build_planning_user_prompt_message(task: str, ui_context_str: str) -> dict[str, str]:
    """Builds the user prompt message for the planning LLM call."""
    user_prompt = f"""
User Task: "{task}"

Current Web Page Context:
{ui_context_str}

Based on the user task and the current web page context, please provide the next action(s) as a JSON object.
"""
    return {"role": "user", "content": user_prompt.strip()}

# --- Assertion Prompts ---

def _build_common_assertion_description() -> str:
    """Describes the assertion task to the LLM."""
    return """
You need to evaluate if a specific assertion about the current web page state is true or false.
The assertion will be given by the user.
You will receive the current state of the web page (URL, title, and a tree of interactive elements).
Based on this information, determine if the assertion holds.

Provide your response as a JSON object conforming to the InsightAssertionResponse schema:
`{"passed": true/false, "reason": "Your detailed explanation for why the assertion passed or failed."}`
Example of a valid JSON response for a passed assertion:
`{{"passed": true, "reason": "The current URL is 'https://www.example.com' which matches the assertion."}}`
Example of a valid JSON response for a failed assertion:
`{{"passed": false, "reason": "The page title is 'Some Other Page' not 'Expected Page Title', so the assertion fails."}}`
Be precise and base your reasoning on the provided context. Do not add any text before or after the JSON object.
"""

def build_assertion_system_prompt_messages() -> List[dict[str, str]]:
    """Builds the system prompt messages for the assertion LLM call."""
    time_zone = get_time_zone_info()
    language = get_language()
    assertion_description = _build_common_assertion_description()

    system_prompt = f"""
You are an expert AI assistant specialized in verifying assertions about web page states.
Current Time Zone: {time_zone}
Language: {language}

You will be given:
1.  An assertion (a statement to verify, e.g., "The URL is https://www.google.com", "The page title contains 'Search Results'").
2.  The current state of the web page (URL, title, and a tree of interactive elements).

Your task is to evaluate if the assertion is true or false based *only* on the provided web page context.

{assertion_description}
    """
    return [{"role": "system", "content": system_prompt.strip()}]

def build_assertion_user_prompt_message(assertion_task: str, ui_context_str: str) -> dict[str, str]:
    """Builds the user prompt message for the assertion LLM call."""
    user_prompt = f"""
Assertion to Verify: "{assertion_task}"

Current Web Page Context:
{ui_context_str}

Based on the assertion and the current web page context, please evaluate if the assertion is true or false.
Provide your response as a JSON object.
"""
    return {"role": "user", "content": user_prompt.strip()}

# Example usage (for testing within this file if needed)
if __name__ == '__main__':
    print("--- Timezone Info ---")
    print(get_time_zone_info())
    print("--- Language Info ---")
    print(get_language())

    print("\n--- Example Planning Prompt ---")
    dummy_context_planning: WebUIContext = {
        "url": "https://www.example.com",
        "size": {"width": 1280, "height": 720, "dpr": 1},
        "screenshotBase64": "dummy_screenshot_data",
        "tree": {"node": None, "children": []}, # Simplified
        "content": [] # Simplified
    }
    ui_desc_plan = describe_ui_context_for_llm(dummy_context_planning)
    planning_prompt = system_prompt_to_task_planning_py(
        page_type="chrome-extension-proxy",
        ui_context_description=ui_desc_plan,
        user_instruction="Search for 'midscene' and press enter."
    )
    # print(json.dumps(planning_prompt, indent=2))

    print("\n--- Example Assertion Prompt ---")
    dummy_context_assert: WebUIContext = {
        "url": "https://www.example.com/search?q=midscene",
        "size": {"width": 1280, "height": 720, "dpr": 1},
        "screenshotBase64": "dummy_screenshot_data_after_search",
        "tree": {"node": None, "children": []},
        "content": []
    }
    ui_desc_assert = describe_ui_context_for_llm(dummy_context_assert)
    assertion_prompt_messages = system_prompt_to_assert_py(
        ui_context_description=ui_desc_assert,
        assertion_prompt="The URL should contain 'q=midscene'"
    )
    # print(json.dumps(assertion_prompt_messages, indent=2))

    print("\n--- Example Planning Prompt ---")
    sample_element_tree = {
        "node": {"element_id": "doc_root", "description": "Document Root", "attributes": {}},
        "children": [
            {
                "node": {"element_id": "search_form_1", "description": "Search form area", "attributes": {"role": "form"}},
                "children": [
                    {
                        "node": {
                            "element_id": "search_input_2", 
                            "description": "Search input field", 
                            "attributes": {"type": "text", "name": "q", "aria-label": "Search query"}
                        },
                        "children": []
                    },
                    {
                        "node": {
                            "element_id": "submit_btn_3", 
                            "description": "Search button", 
                            "attributes": {"type": "submit", "value": "Search"}
                        },
                        "children": []
                    }
                ]
            },
            {
                "node": {"element_id": "link_4", "description": "Some link", "attributes": {"href": "/somepage"}},
                "children": []
            }
        ]
    }
    
    sample_ui_context: WebUIContext = {
        "url": "https://www.example.com",
        "title": "Example Page",
        "task_guidance": ["User wants to find information about 'AI assistants'"],
        "tree": sample_element_tree, # type: ignore
        "focused_element_id": "search_input_2"
    }

    ui_context_str_for_prompt = describe_ui_context_for_llm(sample_ui_context)
    # print("\\n--- UI Context String for Prompt ---")
    # print(ui_context_str_for_prompt)
    # print("------------------------------------\\n")

    system_plan_prompts = build_planning_system_prompt_messages()
    user_plan_prompt = build_planning_user_prompt_message(
        task="Search for 'best AI tools' and then click the search button.",
        ui_context_str=ui_context_str_for_prompt
    )

    print("System Prompt (Planning):")
    print(json.dumps(system_plan_prompts, indent=2))
    print("\\nUser Prompt (Planning):")
    print(json.dumps(user_plan_prompt, indent=2))

    print("\\n\\n----- Testing Assertion Prompts -----")
    system_assert_prompts = build_assertion_system_prompt_messages()
    user_assert_prompt = build_assertion_user_prompt_message(
        assertion_task="The page title is 'Example Page'",
        ui_context_str=ui_context_str_for_prompt
    )
    print("System Prompt (Assertion):")
    print(json.dumps(system_assert_prompts, indent=2))
    print("\\nUser Prompt (Assertion):")
    print(json.dumps(user_assert_prompt, indent=2))

    print("\\n\\n----- Testing Element to String -----")
    single_node_element_tree: ElementTreeNode = {
        "node": {"element_id": "input_field_1", "description": "Username input", "attributes": {"type": "text", "name": "username", "placeholder": "Enter username", "value": "testuser"}},
        "children": []
    }
    print(_element_to_string(single_node_element_tree))

    complex_element_tree: ElementTreeNode = {
        "node": {"element_id": "main_div", "description": "Main content area", "attributes": {}},
        "children": [
            single_node_element_tree,
            {
                "node": {"element_id": "button_1", "description": "Submit button", "attributes": {"role": "button", "data-test-id": "submit"}},
                "children": []
            }
        ]
    }
    print(_element_to_string(complex_element_tree))

    # Test empty elements tree
    empty_ui_context: WebUIContext = {
        "url": "https://www.example.com/empty",
        "title": "Empty Page",
        "task_guidance": [],
        "tree": None
    }
    empty_ui_context_str = describe_ui_context_for_llm(empty_ui_context)
    print("\\n--- Empty UI Context String ---")
    print(empty_ui_context_str)
    print("-----------------------------") 