import os
from flask import Flask, request
import threading, time, websocket, requests, json

app = Flask(__name__)

# ==================== 1. 全局配置 ====================
AUTO_MODE = False
DEVICE_ID = os.getenv("DEVICE_ID", "13")
GROUP = os.getenv("GROUP", "6f4f01112918afe457d9d9e9c1c7a331")
SHARE_ID = os.getenv("SHARE_ID", "834697") # 初始ID，之后通过接口热更新

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
                # 心跳保活，防止被踢
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

# ==================== 2. HTTP 控制接口 ====================
@app.route('/cmd')
def cmd():
    """手动控制接口：?m=通道&v=强度"""
    global AUTO_MODE
    motor = request.args.get('m', '1') 
    val = request.args.get('v', '0')
    
    # 急停逻辑
    if int(val) == 0:
        AUTO_MODE = False
        remote.control("1", 0)
        remote.control("3", 0)
        return "ALL STOPPED (EMERGENCY)"
        
    AUTO_MODE = False
    remote.control(motor, val)
    return f"OK: {motor} -> {val}"

@app.route('/auto_on')
def auto_on():
    """开启自动驾驶"""
    global AUTO_MODE
    AUTO_MODE = True
    return "Auto-pilot ON"

@app.route('/auto_off')
def auto_off():
    """关闭自动驾驶"""
    global AUTO_MODE
    AUTO_MODE = False
    remote.control("1", 0)
    remote.control("3", 0)
    return "Auto-pilot OFF"

@app.route('/update_id')
def update_id():
    """热更新ID接口：?id=新ID"""
    global SHARE_ID
    new_id = request.args.get('id')
    if new_id:
        SHARE_ID = str(new_id).strip()
        remote.share_id = SHARE_ID
        remote.bind()
        return f"SHARE_ID 已热更新为: {SHARE_ID}，并已重新绑定。"
    return "请提供 ?id=xxx"

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
    port = int(os.environ.get("PORT", 8080))
    print(f">>> 启动纯 HTTP 服务，端口: {port}")
    app.run(host='0.0.0.0', port=port)
