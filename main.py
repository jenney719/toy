import os
from flask import Flask, request
import threading, time, websocket, requests, json

app = Flask(__name__)

# 配置信息
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
            r = requests.post("https://api.app.knightjenay.cn/kisstoy/remote-control/binding", json={"id": self.share_id}, timeout=5)
            print(f"DEBUG: 绑定结果 {r.status_code}")
        except Exception as e:
            print(f"DEBUG: 绑定失败 {e}")

    def connect(self):
        def run():
            url = f"wss://api.app.knightjenay.cn/websocket-kisstoy?group={self.group}"
            self.ws = websocket.WebSocketApp(url,
                on_open=lambda ws: (print("!!! WS 连接成功 !!!"), setattr(self, 'is_connected', True)),
                on_error=lambda ws, e: print(f"!!! WS 错误: {e} !!!"),
                on_close=lambda ws, *args: (print("!!! WS 断开 !!!"), setattr(self, 'is_connected', False)))
            self.ws.run_forever()
        threading.Thread(target=run, daemon=True).start()

    def control(self, motor, intensity):
        if not self.is_connected:
            print("DEBUG: 尝试发送但 WS 未连接")
            return
        cmd = {"event": "control", "data": {"target": self.group, "device_id": self.device_id, "motors": {str(motor): int(intensity)}}}
        self.ws.send(json.dumps(cmd))
        print(f"DEBUG: 已发送指令 -> {intensity}")

remote = KisstoyRemote(DEVICE_ID, GROUP, SHARE_ID)

@app.route('/cmd')
def cmd():
    motor = request.args.get('m', '1')
    val = request.args.get('v', '0')
    remote.control(motor, val)
    return "OK"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

