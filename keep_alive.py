import os
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.get("/")
def home():
    return "OK"

def _run():
    port = int(os.environ.get("PORT", "3000"))
    print(f"🌐 Keep-alive escuchando en 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    Thread(target=_run, daemon=True).start()


