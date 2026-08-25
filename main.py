import os
from flask import Flask, request
import threading, time, websocket, requests, json

app = Flask(__name__)

# ==================== 1. 全局配置 & 双模状态 ====================
AUTO_MODE = False
DEVICE_ID = os.getenv("DEVICE_ID", "13")
GROUP = os.getenv("GROUP", "6f4f01112918afe457d9d9e9c1c7a331")
SHARE_ID = os.getenv("SHARE_ID", "834697")

class KisstoyRemote:
    def __init__(self, device_id, group, share_id):
        self.device_id = str(device_id)
        self.group = str(group)
        self.share_id = str(share_id)
        self.ws = None
        self.is_connected = False
        self.connect()

    # ==================== 2. 权限绑定逻辑 ====================
    def bind(self):
        try:
            r = requests.post("https://api.app.knightjenay.cn/kisstoy/remote-control/binding", json={"id": self.share_id}, timeout=5)
            print(f"DEBUG: 授权绑定结果 -> {r.status_code}")
        except Exception as e:
            print(f"DEBUG: 授权绑定异常 -> {e}")

    # ==================== 3. 无限重连 & 心跳防掉线 ====================
    def connect(self):
        def run():
            url = f"wss://api.app.knightjenay.cn/websocket-kisstoy?group={self.group}"
            while True:  # 无限循环：断线自动重连，不死之身
                print(">>> 正在尝试建立云端 WebSocket 通道...")
                self.bind()  # 每次重连前重新绑定，确保会话最新
                self.ws = websocket.WebSocketApp(url,
                    on_open=lambda ws: (print("!!! WS 连通成功，设备已就绪 !!!"), setattr(self, 'is_connected', True)),
                    on_error=lambda ws, e: print(f"!!! WS 错误: {e} !!!"),
                    on_close=lambda ws, *args: (print("!!! WS 连接断开，5秒后自动重连 !!!"), setattr(self, 'is_connected', False)))
                # ping_interval=10 强制每10秒发送心跳包，彻底防止被云端踢掉
                self.ws.run_forever(ping_interval=10, ping_timeout=5)
                time.sleep(5)
        threading.Thread(target=run, daemon=True).start()

    # ==================== 4. 通道指令发送 ====================
    def control(self, motor, intensity):
        if not self.is_connected:
            print(f"DEBUG: 尝试发送指令到通道[{motor}]，但 WS 处于离线状态")
            return False
        cmd = {"event": "control", "data": {"target": self.group, "device_id": self.device_id, "motors": {str(motor): int(intensity)}}}
        try:
            self.ws.send(json.dumps(cmd))
            print(f"DEBUG: 成功发送 -> 通道[{motor}] 强度[{intensity}%]")
            return True
        except Exception as e:
            print(f"DEBUG: 指令发送异常 -> {e}")
            return False

remote = KisstoyRemote(DEVICE_ID, GROUP, SHARE_ID)

# ==================== 5. AI 手动控制接口 & 急停拦截 ====================
@app.route('/cmd')
def cmd():
    global AUTO_MODE
    motor = request.args.get('m', '1') 
    val = request.args.get('v', '0')
    
    # 【核心急停安全逻辑】只要收到任何强度的关闭指令 (v=0)，立刻打断 AI 挂机，并让两个电机全部熄火
    if int(val) == 0:
        AUTO_MODE = False
        remote.control("1", 0)  # 强制关闭 1-振动
        remote.control("3", 0)  # 强制关闭 3-吮吸
        return "ALL STOPPED (EMERGENCY)"
        
    AUTO_MODE = False  # 手动干预时，自动关闭 AI 挂机，切回手动
    remote.control(motor, val)
    return f"OK: {motor} -> {val}"

# ==================== 6. AI 自动驾驶开关 ====================
@app.route('/auto_on')
def auto_on():
    global AUTO_MODE
    AUTO_MODE = True
    return "Auto-pilot ON"

@app.route('/auto_off')
def auto_off():
    global AUTO_MODE
    AUTO_MODE = False
    remote.control("1", 0)
    remote.control("3", 0)
    return "Auto-pilot OFF"

# ==================== 7. 旗舰版自动驾驶算法 (0.1秒级急停检测) ====================
def ai_auto_pilot():
    while True:
        if AUTO_MODE:
            # 节奏段 1：振动舒缓 (持续3秒)
            remote.control("1", 40)
            remote.control("3", 0)
            for _ in range(30):  # 将3秒拆为30个0.1秒，实现毫秒级急停响应
                if not AUTO_MODE: break
                time.sleep(0.1)
            if not AUTO_MODE: continue  # 优雅回到主循环
            
            # 节奏段 2：吮吸增强 (持续2秒)
            remote.control("1", 0)
            remote.control("3", 60)
            for _ in range(20):
                if not AUTO_MODE: break
                time.sleep(0.1)
            if not AUTO_MODE: continue
            
            # 节奏段 3：双通道齐开 (持续1秒)
            remote.control("1", 50)
            remote.control("3", 50)
            for _ in range(10):
                if not AUTO_MODE: break
                time.sleep(0.1)
            if not AUTO_MODE: continue
            
            # 节奏段 4：间歇期停顿 (持续1秒)
            remote.control("1", 0)
            remote.control("3", 0)
            for _ in range(10):
                if not AUTO_MODE: break
                time.sleep(0.1)
        else:
            time.sleep(0.5)  # 空闲状态下低频检索，节省服务器 CPU

threading.Thread(target=ai_auto_pilot, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

   
