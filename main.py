import os
from flask import Flask, request
import threading, time, websocket, requests, json

app = Flask(__name__)

# 全局配置
AUTO_MODE = False
DEVICE_ID = os.getenv("DEVICE_ID", "13")
GROUP = os.getenv("GROUP", "6f4f01112918afe457d9d9e9c1c7a331")
SHARE_ID = os.getenv("SHARE_ID", "834161")

class KisstoyRemote:
    def __init__(self, device_id, group, share_id):
        self.device_id = str(device_id)
        self.group = str(group)
        self.share_id = str(share_id)
        self.ws = None
        self.is_connected = False
        self.bind()
        self.connect()

    def bind(self):
        try:
            requests.post("https://api.app.knightjenay.cn/kisstoy/remote-control/binding", json={"id": self.share_id}, timeout=5)
        except: pass

    def connect(self):
        def run():
            url = f"wss://api.app.knightjenay.cn/websocket-kisstoy?group={self.group}"
            self.ws = websocket.WebSocketApp(url,
                on_open=lambda ws: setattr(self, 'is_connected', True),
                on_close=lambda ws, *args: setattr(self, 'is_connected', False))
            self.ws.run_forever()
        threading.Thread(target=run, daemon=True).start()

    def control(self, motor, intensity):
        if not self.is_connected: return
        self.ws.send(json.dumps({"event": "control", "data": {"target": self.group, "device_id": self.device_id, "motors": {str(motor): int(intensity)}}}))

remote = KisstoyRemote(DEVICE_ID, GROUP, SHARE_ID)

@app.route('/cmd')
def cmd():
    global AUTO_MODE
    AUTO_MODE = False  # 手动指令优先级最高，关闭自动
    motor = request.args.get('m', '1')
    val = request.args.get('v', '0')
    remote.control(motor, val)
    return f"Manual control: {motor} -> {val}"

@app.route('/auto_on')
def auto_on():
    global AUTO_MODE
    AUTO_MODE = True
    return "Auto-pilot ON"

@app.route('/auto_off')
def auto_off():
    global AUTO_MODE
    AUTO_MODE = False
    return "Auto-pilot OFF"

# 自动驾驶模拟线程
def ai_auto_pilot():
    while True:
        if AUTO_MODE:
            # 这里你可以根据需要写更复杂的自主逻辑
            # 简单示例：每5秒随机震动一次
            remote.control("1", 40)
            time.sleep(5)
        time.sleep(2)

threading.Thread(target=ai_auto_pilot, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
