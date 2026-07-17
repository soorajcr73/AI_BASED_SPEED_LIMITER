import http.server
import socketserver
import webbrowser

PORT = 5500

Handler = http.server.SimpleHTTPRequestHandler


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


with ReusableTCPServer(("", PORT), Handler) as httpd:

    print("\nFrontend running successfully!")
    print("\nOpen this link in browser:\n")
    print(f"http://127.0.0.1:{PORT}\n")

    webbrowser.open(f"http://127.0.0.1:{PORT}")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")