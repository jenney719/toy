import os
import threading, time, websocket, requests, json
from mcp.server.fastmcp import FastMCP

# ==================== 1. 全局配置 & 双模状态 ====================
AUTO_MODE = False
DEVICE_ID = os.getenv("DEVICE_ID", "13")
GROUP = os.getenv("GROUP", "6f4f01112918afe457d9d9e9c1c7a331")
SHARE_ID = os.getenv("SHARE_ID", "834697") # 记得换成最新的

class KisstoyRemote:
    def __init__(self, device_id, group, share_id):
        self.device_id = str(device_id)
        self.group = str(group)
        self.share_id = str(share_id)
        self.ws = None
        self.is_connected = False
        self.connect()

    def bind(self):
        try:
            requests.post("https://api.app.knightjenay.cn/kisstoy/remote-control/binding", json={"id": self.share_id}, timeout=5)
        except: pass

    def connect(self):
        def run():
            url = f"wss://api.app.knightjenay.cn/websocket-kisstoy?group={self.group}"
            while True:
                self.bind()
                self.ws = websocket.WebSocketApp(url,
                    on_open=lambda ws: setattr(self, 'is_connected', True),
                    on_close=lambda ws, *args: setattr(self, 'is_connected', False))
                self.ws.run_forever(ping_interval=10, ping_timeout=5)
                time.sleep(5)
        threading.Thread(target=run, daemon=True).start()

    def control(self, motor, intensity):
        if not self.is_connected: return False
        cmd = {"event": "control", "data": {"target": self.group, "device_id": self.device_id, "motors": {str(motor): int(intensity)}}}
        try:
            self.ws.send(json.dumps(cmd))
            return True
        except: return False

remote = KisstoyRemote(DEVICE_ID, GROUP, SHARE_ID)

# ==================== 2. 创建 MCP 服务端 ====================
# 这里是核心改变：不再用 Flask 路由，而是用 MCP 工具
mcp = FastMCP("Kisstoy-Controller")

@mcp.tool()
def control_device(motor: int, intensity: int) -> str:
    """
    控制物理设备。
    参数 motor: 1代表 zhendong，3代表 shunxi。
    参数 intensity: 0-100的强度数值。如果是0代表紧急停止。
    """
    global AUTO_MODE
    if intensity == 0:
        AUTO_MODE = False
        remote.control("1", 0)
        remote.control("3", 0)
        return "已触发急停，全部通道已关闭。"
        
    AUTO_MODE = False
    remote.control(str(motor), intensity)
    return f"通道 {motor} 已调整为 {intensity}% 强度"

@mcp.tool()
def set_auto_pilot(enable: bool) -> str:
    """
    开启或关闭自动挂机模式 (交替 zhendong 和 shunxi)。
    参数 enable: true为开启，false为彻底关闭并关机。
    """
    global AUTO_MODE
    if enable:
        AUTO_MODE = True
        return "自动挂机已开启，正在按节奏运行。"
    else:
        AUTO_MODE = False
        remote.control("1", 0)
        remote.control("3", 0)
        return "自动挂机已关闭，设备已停息。"

# ==================== 3. 自动驾驶线程 ====================
def ai_auto_pilot():
    while True:
        if AUTO_MODE:
            remote.control("1", 40)
            remote.control("3", 0)
            for _ in range(30):
                if not AUTO_MODE: break
                time.sleep(0.1)
            if not AUTO_MODE: continue
            
            remote.control("1", 0)
            remote.control("3", 60)
            for _ in range(20):
                if not AUTO_MODE: break
                time.sleep(0.1)
            if not AUTO_MODE: continue
            
            remote.control("1", 50)
            remote.control("3", 50)
            for _ in range(10):
                if not AUTO_MODE: break
                time.sleep(0.1)
            if not AUTO_MODE: continue
            
            remote.control("1", 0)
            remote.control("3", 0)
            for _ in range(10):
                if not AUTO_MODE: break
                time.sleep(0.1)
        else:
            time.sleep(0.5)

threading.Thread(target=ai_auto_pilot, daemon=True).start()

# ==================== 4. 启动服务 ====================
if __name__ == '__main__':
    # 获取 Railway 分配的端口
    port = int(os.environ.get("PORT", 8080))
    # 以 SSE 模式启动 MCP 服务
    mcp.run(transport="sse", host="0.0.0.0", port=port)
