"""常量和公共定义"""

# 默认桥接服务器端口，与TS源码保持一致
DefaultBridgeServerPort = 3766
# Socket.IO端点
DefaultLocalEndpoint = f"http://127.0.0.1:{DefaultBridgeServerPort}"
# 备用端点
BackupEndpoints = [
    f"ws://127.0.0.1:{DefaultBridgeServerPort}",
    f"ws://127.0.0.1:{DefaultBridgeServerPort}/bridge",
    f"ws://127.0.0.1:{DefaultBridgeServerPort}/ws"
]
BridgeCallTimeout = 30000  # 30秒

class BridgeEvent:
    """桥接事件类型"""
    Call = "bridge-call"
    CallResponse = "bridge-call-response"
    UpdateAgentStatus = "bridge-update-agent-status"
    Message = "bridge-message"
    Connected = "bridge-connected"
    Refused = "bridge-refused"
    ConnectNewTabWithUrl = "connectNewTabWithUrl"
    ConnectCurrentTab = "connectCurrentTab"
    GetBrowserTabList = "getBrowserTabList"
    SetDestroyOptions = "setDestroyOptions"
    SetActiveTabId = "setActiveTabId"

# 终止信号
BridgeSignalKill = "MIDSCENE_BRIDGE_SIGNAL_KILL"

class MouseEvent:
    """鼠标事件类型"""
    PREFIX = "mouse."
    Click = "mouse.click"
    Wheel = "mouse.wheel"
    Move = "mouse.move"
    Drag = "mouse.drag"

class KeyboardEvent:
    """键盘事件类型"""
    PREFIX = "keyboard."
    Type = "keyboard.type"
    Press = "keyboard.press"

# 桥接页面类型
BridgePageType = "page-over-chrome-extension-bridge"

# 错误代码
BridgeErrorCodeNoClientConnected = "no-client-connected"

# 当前版本
BRIDGE_VERSION = "0.1.0"

# WebSocket协议版本
ProtocolVersion = "1.0" 