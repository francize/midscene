"""共享类型定义"""
from typing import TypedDict, List, Tuple, Dict, Any, Optional, Union

class WebElementInfo(TypedDict, total=False):
    """Web元素信息"""
    id: str
    rect: Dict[str, int]
    center: Tuple[int, int]
    content: str
    attributes: Dict[str, Any]
    locator: Optional[str]
    indexId: int

class ElementTreeNode(TypedDict, total=False):
    """元素树节点"""
    node: Optional[WebElementInfo]
    children: List['ElementTreeNode']

class WebUIContext(TypedDict, total=False):
    """Web UI上下文"""
    content: List[WebElementInfo]
    tree: ElementTreeNode
    size: Dict[str, Union[int, float]]
    screenshotBase64: str
    url: str
    title: Optional[str]

class PlanningAction(TypedDict, total=False):
    """计划动作"""
    type: str
    thought: Optional[str]
    param: Any
    locate: Optional[Dict[str, Any]]

class PlanResponse(TypedDict):
    """计划响应"""
    actions: List[PlanningAction]
    reasoning: str

class InsightAssertionResponse(TypedDict):
    """断言响应"""
    passed: bool
    reason: str 