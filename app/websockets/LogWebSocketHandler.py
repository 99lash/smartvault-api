from fastapi import WebSocket, WebSocketDisconnect
from app.schemas.LogCreate import LogCreate
from app.services.Logs.LogService import LogService
from app.services.Logs.AuthHandlerService import AuthHandlerService
from app.models.Log import LogEventType
from app.core.database import SessionLocal

class LogWebSocketHandler:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def handle_connection(self):
        """
        Main handler for /logs/ws connections.
        Accepts, loops for messages, dispatches events.
        """
        await self.websocket.accept()
        try:
            while True:
                raw_data = await self.websocket.receive_text()
                try:
                    payload = LogCreate.model_validate_json(raw_data)
                    with SessionLocal() as db:
                        service = LogService(db)
                        auth_handler = AuthHandlerService(service)
                        
                        if payload.event_type == LogEventType.unlock and payload.details:
                            response = auth_handler.handle_unlock_request(payload)
                            await self.websocket.send_json(response)
                        
                        elif payload.event_type == LogEventType.failed_attempt and payload.details:
                            new_log = service.log_failed_unlock_attempt(
                                vault_id=payload.vault_id,
                                user_id=None,  # Anonymous for failed attempts
                                reason=payload.details
                            )
                            service.clear_sessions_for_vault(payload.vault_id)
                            await self.websocket.send_json({"status": "ok", "event_type": "failed_attempt"})
                        
                        elif payload.event_type == LogEventType.tamper and payload.details:
                            new_log = service.log_tamper_detection(
                                vault_id=payload.vault_id,
                                sensor_data=payload.details
                            )
                            service.clear_sessions_for_vault(payload.vault_id)
                            await self.websocket.send_json({"status": "ok", "event_type": "tamper"})
                        
                        else:
                            new_log = service.create_log(
                                vault_id=payload.vault_id,
                                event_type=payload.event_type,
                                user_id=None,  # Default to anonymous
                                details=payload.details,
                            )
                            if new_log:
                                await self.websocket.send_json({"status": "ok", "event_type": new_log.event_type.value})
                            else:
                                await self.websocket.send_json({"status": "error", "message": "Invalid event_type or details"})
                
                except Exception as e:
                    await self.websocket.send_json({"status": "error", "error": str(e)})
        
        except WebSocketDisconnect:
            print("WebSocket disconnected: /logs/ws")