import socket
import threading
import time

import webview

from app import create_app


def get_free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def run_server(app, port):
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


def main():
    app = create_app()
    port = get_free_port()

    server_thread = threading.Thread(target=run_server, args=(app, port), daemon=True)
    server_thread.start()

    # Espera corta para asegurar que Flask levante antes de abrir la ventana.
    time.sleep(0.6)

    webview.create_window(
        title="KinoAnalytica",
        url=f"http://127.0.0.1:{port}",
        width=1400,
        height=900,
        min_size=(1100, 700),
    )
    webview.start()


if __name__ == "__main__":
    main()
