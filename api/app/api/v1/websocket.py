"""
WebSocket endpoint for real-time metrics updates
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import text, select
import json
import asyncio
from app.core.security import decode_access_token
router = APIRouter()

# Store active connections with account_id mapping
active_connections: dict[WebSocket, str] = {}


@router.websocket("/metrics")
async def websocket_metrics(
    websocket: WebSocket,
):
    """
    WebSocket endpoint for real-time metrics updates.
    Clients receive updates when calls are ingested or metrics change.
    """
    await websocket.accept()
    
    try:
        # Wait for auth message
        auth_msg = await websocket.receive_text()
        auth_data = json.loads(auth_msg)
        if auth_data.get("type") != "auth":
            await websocket.close(code=1008, reason="Authentication required")
            return
        
        try:
            payload = decode_access_token(auth_data.get("token"))
            user_id = payload.get("sub")
            if not user_id:
                raise ValueError("No user ID in token")
        except Exception as e:
            await websocket.close(code=1008, reason="Invalid token")
            return
        
        # Get user to determine account_id
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            from app.models.user import User
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                await websocket.close(code=1008, reason="User not found")
                return
            account_id = str(user.account_id)
        
        # Store connection with account_id
        active_connections[websocket] = account_id
        
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "account_id": account_id,
        })
        
        # Keep connection alive and forward notifications
        # In production, this would use Postgres LISTEN/NOTIFY properly
        while True:
            try:
                # Wait for client messages (ping/pong, etc.)
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                data = json.loads(message)
                
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({"type": "keepalive"})
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        active_connections.pop(websocket, None)


async def broadcast_metrics_update(message: dict):
    """Broadcast metrics update to connected clients for the specified account"""
    account_id = message.get("account_id")
    if not account_id:
        return
    
    disconnected = []
    for connection, conn_account_id in list(active_connections.items()):
        # Only send to clients from the same account
        if conn_account_id == account_id:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
    
    # Clean up disconnected clients
    for conn in disconnected:
        active_connections.pop(conn, None)

