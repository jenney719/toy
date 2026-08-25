import os
from flask import Flask, request
import threading, time, websocket, requests, json

app = Flask(__name__)

# 配置
DEVICE_ID = os.getenv("DEVICE_ID", "13")
GROUP = os.getenv("GROUP", "6f4f01112918afe457d9d9e9c1c7a331")
SHARE_ID = os.getenv("SHARE_ID", "834313")

class KisstoyRemote:
    def __init__(self, device_id, group, share_id):
        self.device_id = str(device_id)
        self.group = str(group)
        self.share_id = str(share_id)
        self.ws = None
        self.is_connected = False
        self.connect()

    def connect(self):
        def run():
            # 每次连接前重新绑定，确保 ID 有效
            try:
                requests.post("https://api.app.knightjenay.cn/kisstoy/remote-control/binding", json={"id": self.share_id}, timeout=5)
            except: pass
            
            url = f"wss://api.app.knightjenay.cn/websocket-kisstoy?group={self.group}"
            self.ws = websocket.WebSocketApp(url,
                on_open=lambda ws: (print("!!! WS 连接成功 !!!"), setattr(self, 'is_connected', True)),
                on_close=lambda ws, *args: (print("!!! WS 断开 !!!"), setattr(self, 'is_connected', False)))
            # 增加 ping_interval，防止服务器因为没心跳而踢人
            self.ws.run_forever(ping_interval=10, ping_timeout=5)
            
        threading.Thread(target=run, daemon=True).start()

    def control(self, motor, intensity):
        if not self.is_connected:
            print("DEBUG: WS 未连接，重试中...")
            return False
        cmd = {"event": "control", "data": {"target": self.group, "device_id": self.device_id, "motors": {str(motor): int(intensity)}}}
        self.ws.send(json.dumps(cmd))
        return True

remote = KisstoyRemote(DEVICE_ID, GROUP, SHARE_ID)

@app.route('/cmd')
def cmd():
    motor = request.args.get('m', '1')
    val = request.args.get('v', '0')
    if remote.control(motor, val):
        return "OK: Sent"
    else:
        return "Error: WS Not Connected, try again in 5s"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
