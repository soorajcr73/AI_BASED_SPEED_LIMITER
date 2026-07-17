from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio

app = FastAPI()

clients = []


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    print("FRONTEND CONNECTED")

    await websocket.accept()
    clients.append(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            await broadcast(data)
    except WebSocketDisconnect:

        print("CLIENT DISCONNECTED")

        if websocket in clients:
            clients.remove(websocket)


async def broadcast(message):

    disconnected_clients = []

    for client in clients:
        try:
            await client.send_text(message)
        except:
            disconnected_clients.append(client)

    for dc in disconnected_clients:
        clients.remove(dc)