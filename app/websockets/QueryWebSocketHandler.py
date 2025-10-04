from fastapi import WebSocket, WebSocketDisconnect
from app.schemas.LogSchemas import WSQueryRequest
from app.services.logs.LogQueryService import LogQueryService
from app.core.database import SessionLocal

class QueryWebSocketHandler:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def handle_connection(self):
        await self.websocket.accept()
        try:
            # Receive initial query parameters from client
            raw_data = await self.websocket.receive_text()
            try:
                query_params = WSQueryRequest.model_validate_json(raw_data)
                
                # Use a new DB session for the query
                with SessionLocal() as db:
                    service = LogQueryService(db)
                    logs = service.get_filtered_logs_by_vault(str(query_params.vault_id), query_params.prefixes)
                    
                    # Send the filtered logs as response
                    response = {
                        "status": "ok",
                        "vault_id": query_params.vault_id,
                        "prefixes": query_params.prefixes,
                        "logs": logs
                    }
                    await self.websocket.send_json(response)
                
                # Keep connection open for potential additional messages (e.g., refresh)
                while True:
                    # Wait for client messages; extend for real-time if needed
                    msg = await self.websocket.receive_text()
                    if msg == "refresh":
                        # Re-fetch and send updated logs
                        with SessionLocal() as db_refresh:
                            service_refresh = LogQueryService(db_refresh)
                            updated_logs = service_refresh.get_filtered_logs_by_vault(str(query_params.vault_id), query_params.prefixes)
                            update_resp = {
                                "status": "ok",
                                "type": "refresh",
                                "logs": updated_logs
                            }
                            await self.websocket.send_json(update_resp)
                    elif msg == "close":
                        break
                    else:
                        await self.websocket.send_json({"status": "error", "message": "Unknown command"})
                        
            except ValueError as e:
                # Validation error for query params
                await self.websocket.send_json({"status": "error", "message": f"Invalid query parameters: {str(e)}"})
            
        except WebSocketDisconnect:
            print("WebSocket disconnected: /logs/ws/query")
        except Exception as e:
            await self.websocket.send_json({"status": "error", "error": str(e)})