import os
import threading, time, websocket, requests, json
from mcp.server.fastmcp import FastMCP

# ==================== 0. 让 FastMCP 从环境变量读取监听地址和端口 ====================
# Railway 会自动注入 PORT 环境变量，这里兜底为 8000
os.environ.setdefault("FASTMCP_PORT", os.environ.get("PORT", "8000"))
os.environ.setdefault("FASTMCP_HOST", "0.0.0.0")

# ==================== 1. 全局配置 ====================
AUTO_MODE = False
DEVICE_ID = os.getenv("DEVICE_ID", "13")
GROUP = os.getenv("GROUP", "6f4f01112918afe457d9d9e9c1c7a331")
SHARE_ID = os.getenv("SHARE_ID", "834697")  # 初始 ID，之后可用 update_share_id 热更新

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
            r = requests.post("https://api.app.knightjenay.cn/kisstoy/remote-control/binding",
                              json={"id": self.share_id}, timeout=5)
            print(f"DEBUG: 授权绑定结果 -> {r.status_code}")
        except Exception as e:
            print(f"DEBUG: 授权绑定异常 -> {e}")

    def connect(self):
        def run():
            url = f"wss://api.app.knightjenay.cn/websocket-kisstoy?group={self.group}"
            while True:
                print(">>> 正在尝试建立云端 WebSocket 通道...")
                self.bind()
                self.ws = websocket.WebSocketApp(url,
                    on_open=lambda ws: (print("!!! WS 连通成功，设备已就绪 !!!"), setattr(self, 'is_connected', True)),
                    on_error=lambda ws, e: print(f"!!! WS 错误: {e} !!!"),
                    on_close=lambda ws, *args: (print("!!! WS 断开，5秒后重连 !!!"), setattr(self, 'is_connected', False)))
                # 心跳保活，防止被云端踢掉
                self.ws.run_forever(ping_interval=10, ping_timeout=5)
                time.sleep(5)
        threading.Thread(target=run, daemon=True).start()

    def control(self, motor, intensity):
        if not self.is_connected:
            print(f"DEBUG: 尝试发送指令到通道[{motor}]，但 WS 处于离线状态")
            return False
        cmd = {"event": "control", "data": {"target": self.group, "device_id": self.device_id,
               "motors": {str(motor): int(intensity)}}}
        try:
            self.ws.send(json.dumps(cmd))
            print(f"DEBUG: 成功发送 -> 通道[{motor}] 强度[{intensity}%]")
            return True
        except Exception as e:
            print(f"DEBUG: 指令发送异常 -> {e}")
            return False

remote = KisstoyRemote(DEVICE_ID, GROUP, SHARE_ID)

# ==================== 2. MCP 服务端 ====================
mcp = FastMCP("Kisstoy-Controller")

@mcp.tool()
def control_device(motor: int, intensity: int) -> str:
    """
    控制物理设备。motor=1 代表振动，motor=3 代表吮吸。
    intensity 范围为 0-100。传 0 表示紧急停止并关闭所有通道。
    """
    global AUTO_MODE
    if intensity == 0:
        AUTO_MODE = False
        remote.control("1", 0)
        remote.control("3", 0)
        return "已触发急停，全部通道已关闭。"
    AUTO_MODE = False
    remote.control(str(motor), intensity)
    return f"通道 {motor} 已调整为 {intensity}% 强度。"

@mcp.tool()
def set_auto_pilot(enable: bool) -> str:
    """
    开启或关闭自动挂机模式（交替振动和吮吸）。
    enable=true 开启，enable=false 彻底关闭并关机。
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

@mcp.tool()
def update_share_id(new_id: str) -> str:
    """
    当用户的分享链接 ID 发生变化时使用，热更新最新的 SHARE_ID 并立即重新绑定。
    参数 new_id: 从手机分享链接里拿到的最新 id 数字字符串。
    """
    global SHARE_ID
    try:
        SHARE_ID = str(new_id).strip()
        remote.share_id = SHARE_ID
        print(f"DEBUG: 正在热更新 SHARE_ID 为新值: {SHARE_ID}")
        remote.bind()
        return f"SHARE_ID 已更新为 {SHARE_ID}，正在用新 ID 重新绑定。"
    except Exception as e:
        return f"更新失败: {e}"

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

# ==================== 4. 启动服务（关键修正） ====================
if __name__ == '__main__':
    print(">>> 启动 MCP 服务 (streamable-http 模式)")
    print(f">>> 监听端口由环境变量 FASTMCP_PORT 决定: {os.environ.get('FASTMCP_PORT')}")
    # 只传 transport，绝不再传 host/port，避免 TypeError
    mcp.run(transport="streamable-http")
