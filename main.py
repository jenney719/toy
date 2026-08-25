import os
from flask import Flask, request
import threading, time, websocket, requests, json

app = Flask(__name__)

# 定义 Kisstoy 类 (保持不变)
class KisstoyRemote:
    def __init__(self, device_id, group, share_id):
        self.device_id = str(device_id)
        self.group = str(group)
        self.share_id = str(share_id)
        self.ws = None
        self.is_connected = False

    def bind(self):
        try:
            requests.post("https://api.app.knightjenay.cn/kisstoy/remote-control/binding", json={"id": self.share_id}, timeout=5)
        except: pass

    def connect(self):
        def run():
            self.ws = websocket.WebSocketApp(f"wss://api.app.knightjenay.cn/websocket-kisstoy?group={self.group}",
                on_open=lambda ws: setattr(self, 'is_connected', True),
                on_close=lambda ws, *args: setattr(self, 'is_connected', False))
            self.ws.run_forever()
        threading.Thread(target=run, daemon=True).start()

    def control(self, motor, intensity):
        if not self.is_connected: return
        self.ws.send(json.dumps({"event": "control", "data": {"target": self.group, "device_id": self.device_id, "motors": {str(motor): int(intensity)}}}))

# 初始化
remote = KisstoyRemote(os.getenv("DEVICE_ID"), os.getenv("GROUP"), os.getenv("SHARE_ID"))
remote.bind()
remote.connect()

@app.route('/cmd')
def cmd():
    motor = request.args.get('m', '1')
    val = request.args.get('v', '0')
    remote.control(motor, val)
    return "OK"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
