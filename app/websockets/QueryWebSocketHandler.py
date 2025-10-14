from fastapi import WebSocket, WebSocketDisconnect
from app.schemas.LogSchemas import WSQueryRequest
from app.services.logs.LogQueryService import LogQueryService
from app.core.database import get_db_manual
import logging

class QueryWebSocketHandler:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.db_sessions = []  # ✅ Track all DB sessions for cleanup
    
    def _create_db_session(self):
        """Create and track a new DB session"""
        db = get_db_manual()
        self.db_sessions.append(db)
        return db
    
    def _close_db_session(self, db):
        """Close and remove a specific DB session"""
        try:
            db.close()
            if db in self.db_sessions:
                self.db_sessions.remove(db)
        except Exception as e:
            logging.error(f"Error closing DB session: {e}")
    
    async def cleanup(self):
        """
        ✅ CRITICAL: Close all open database sessions
        Called by the route handler in finally block
        """
        logging.info(f"Cleaning up QueryWebSocketHandler - {len(self.db_sessions)} sessions to close")
        for db in self.db_sessions[:]:  # Use slice to avoid modification during iteration
            try:
                db.close()
                logging.info("DB session closed")
            except Exception as e:
                logging.error(f"Error closing DB session during cleanup: {e}")
        self.db_sessions.clear()
        logging.info("QueryWebSocketHandler cleanup complete")

    async def handle_connection(self):
        """
        Handle WebSocket connection for querying filtered logs.
        Supports initial query and refresh commands.
        """
        await self.websocket.accept()
        logging.info("QueryWebSocket connection accepted")
        
        query_params = None
        
        try:
            # Receive initial query parameters from client
            raw_data = await self.websocket.receive_text()
            
            try:
                query_params = WSQueryRequest.model_validate_json(raw_data)
                logging.info(f"Query params: vault_id={query_params.vault_id}, prefixes={query_params.prefixes}")
                
                # ✅ Create tracked DB session
                db = self._create_db_session()
                
                try:
                    service = LogQueryService(db)
                    logs = service.get_filtered_logs_by_vault(
                        str(query_params.vault_id), 
                        query_params.prefixes
                    )
                    
                    # Send the filtered logs as response
                    response = {
                        "status": "ok",
                        "vault_id": query_params.vault_id,
                        "prefixes": query_params.prefixes,
                        "logs": logs
                    }
                    await self.websocket.send_json(response)
                    logging.info(f"Initial query successful, sent {len(logs)} logs")
                
                except Exception as e:
                    logging.error(f"Error fetching logs: {e}")
                    await self.websocket.send_json({
                        "status": "error", 
                        "message": f"Failed to fetch logs: {str(e)}"
                    })
                finally:
                    # ✅ Close session immediately after use
                    self._close_db_session(db)
                
                # Keep connection open for potential additional messages (e.g., refresh)
                while True:
                    msg = await self.websocket.receive_text()
                    logging.info(f"Received command: {msg}")
                    
                    if msg == "refresh":
                        # ✅ Create NEW session for refresh
                        db_refresh = self._create_db_session()
                        
                        try:
                            service_refresh = LogQueryService(db_refresh)
                            updated_logs = service_refresh.get_filtered_logs_by_vault(
                                str(query_params.vault_id), 
                                query_params.prefixes
                            )
                            
                            update_resp = {
                                "status": "ok",
                                "type": "refresh",
                                "logs": updated_logs
                            }
                            await self.websocket.send_json(update_resp)
                            logging.info(f"Refresh successful, sent {len(updated_logs)} logs")
                        
                        except Exception as e:
                            logging.error(f"Error refreshing logs: {e}")
                            await self.websocket.send_json({
                                "status": "error", 
                                "message": f"Failed to refresh logs: {str(e)}"
                            })
                        finally:
                            # ✅ Close refresh session immediately
                            self._close_db_session(db_refresh)
                    
                    elif msg == "close":
                        logging.info("Client requested connection close")
                        break
                    
                    else:
                        await self.websocket.send_json({
                            "status": "error", 
                            "message": "Unknown command. Valid commands: 'refresh', 'close'"
                        })
                        
            except ValueError as e:
                # Validation error for query params
                logging.warning(f"Invalid query parameters: {e}")
                await self.websocket.send_json({
                    "status": "error", 
                    "message": f"Invalid query parameters: {str(e)}"
                })
            
        except WebSocketDisconnect:
            logging.info("WebSocket disconnected: /logs/ws/query")
        except Exception as e:
            logging.error(f"QueryWebSocket error: {e}")
            try:
                await self.websocket.send_json({
                    "status": "error", 
                    "error": str(e)
                })
            except:
                # Connection might already be closed
                pass