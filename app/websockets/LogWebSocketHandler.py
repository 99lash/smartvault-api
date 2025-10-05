from fastapi import WebSocket, WebSocketDisconnect
from app.schemas.log import LogCreate
from app.services.Logs.LogService import LogService
from app.services.Logs.AuthHandlerService import AuthHandlerService
from app.services.Logs.VaultAccessControllerService import VaultAccessController
from app.services.Logs.LogQueryService import LogQueryService
from app.services.users.UserService import UserService
from app.repositories.VaultMembershipRepository import VaultMembershipRepository
from app.models.Log import LogEventType
from app.core.database import SessionLocal
import logging

class LogWebSocketHandler:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def handle_connection(self):
        """
        Main handler for /logs/ws connections.
        Accepts, loops for messages, dispatches events.
        Supports query mode if prefixes param present (for log retrieval with auth).
        """
        import logging
        print("WS: Connection attempt")
        logging.info(f"WS connection attempt from {self.websocket.client.host}")
        await self.websocket.accept()
        print("WS: Connection accepted")
        logging.info("WS connection accepted")
        
        # Check for query mode (log retrieval with auth)
        query_params = self.websocket.query_params
        token = query_params.get('token')
        vault_id_str = str(query_params.get('vault_id'))
        prefixes_str = query_params.get('prefixes', '')
        
        token_preview = token[:20] + "..." if token else "None"
        prefixes_preview = prefixes_str[:50] + "..." if prefixes_str else "None"
        print(f"WS: Extracted query params - token present: {bool(token)}, full token masked: {token_preview}, vault_id: {vault_id_str}, prefixes: {prefixes_preview}")
        logging.info(f"Query params details: token length={len(token) if token else 0}, vault_id={vault_id_str}, prefixes={prefixes_str}")
        
        if prefixes_str and token and vault_id_str:
            print("WS: Entering query mode")
            logging.info("Detected query mode")
            try:
                vault_id = vault_id_str
                prefixes = [p.strip() for p in prefixes_str.split(',') if p.strip()]
                print(f"WS: Parsed vault_id={vault_id}, prefixes={prefixes}")
                
                db = next(get_db_ws())
                print(f"WS: Starting connection for vault_id={vault_id}")
                print(f"WS: Token received: {token[:20]}...")
                print(f"WS: Opening session...")
                print(f"WS: About to validate token...")
                # Validate token and get user
                try:
                    logging.info(f"Attempting to validate WS token for vault {vault_id}: {token[:20]}...")
                    user = UserService.validate_token(token, db)
                    print(f"WS: Token validation succeeded for user {user.username}, id {user.id}")
                    logging.info(f"Token validated for user {user.username}, user_id: {user.id}")
                except ValueError as auth_err:
                    print(f"WS: Token validation FAILED with ValueError: {str(auth_err)} - full details: {auth_err}")
                    import traceback
                    traceback.print_exc()
                    logging.warning(f"WS auth failed for vault {vault_id}: {auth_err} - traceback: {traceback.format_exc()}")
                    await self.websocket.send_json({"status": "error", "message": "Invalid token", "details": str(auth_err)})
                    await self.websocket.close(code=status.WS_403_FORBIDDEN)
                    db.close()
                    return
                except Exception as general_err:
                    print(f"WS: Unexpected error in token validation: {str(general_err)}")
                    import traceback
                    traceback.print_exc()
                    logging.error(f"WS token validation unexpected error: {general_err} - traceback: {traceback.format_exc()}")
                    await self.websocket.send_json({"status": "error", "message": "Token validation error", "details": str(general_err)})
                    await self.websocket.close(code=status.WS_403_FORBIDDEN)
                    db.close()
                    return
                
                # Check vault access
                print(f"WS: Checking vault access for user {user.id} (username: {user.username}), vault {vault_id}")
                vault_membership_repo = VaultMembershipRepository(db)
                controller = VaultAccessController(vault_membership_repo)
                access_result = controller.check_access(user.id, vault_id)
                print(f"WS: Vault access check result: {access_result} for user {user.id}, vault {vault_id}")
                if not access_result:
                    print(f"WS: Access DENIED for user {user.id} to vault {vault_id} - no UserVault relation found?")
                    logging.warning(f"User {user.username} denied access to vault {vault_id} - check UserVault table")
                    await self.websocket.send_json({"status": "error", "message": "No access to vault", "vault_id": vault_id, "user_id": user.id})
                    await self.websocket.close(code=status.WS_403_FORBIDDEN)
                    db.close()
                    return
                print(f"WS: Access GRANTED, proceeding to fetch logs")
                logging.info(f"Vault access confirmed for user {user.username}, vault {vault_id}")
                
                # Fetch filtered logs
                log_query_service = LogQueryService(db)
                logs = log_query_service.get_filtered_logs_by_vault(vault_id, prefixes)
                
                response = {
                    "status": "ok",
                    "vault_id": vault_id,
                    "prefixes": prefixes,
                    "logs": logs
                }
                await self.websocket.send_json(response)
                print(f"WS: Query successful, sent {len(logs)} logs")
                logging.info(f"WS query successful for user {user.username}, vault {vault_id}, {len(logs)} logs sent")
                db.close()
                print("WS: Scoped session closed, entering event loop")
                
            except ValueError as ve:
                print(f"WS: ValueError in query mode: {str(ve)} - likely invalid vault_id or prefixes parsing")
                import traceback
                traceback.print_exc()
                logging.error(f"WS query param error: {ve} - traceback: {traceback.format_exc()}")
                await self.websocket.send_json({"status": "error", "message": "Invalid vault_id or prefixes", "details": str(ve)})
            except Exception as e:
                print(f"WS: Unexpected Exception in query mode: {str(e)}")
                import traceback
                traceback.print_exc()
                logging.error(f"WS query error: {e} - traceback: {traceback.format_exc()}")
                await self.websocket.send_json({"status": "error", "error": str(e), "traceback": traceback.format_exc()})
            
            # Keep open for potential realtime events or client subscribe
            logging.info("Query mode completed, entering event loop")
        
        # Normal event handling (or continue after query)
        try:
            while True:
                raw_data = await self.websocket.receive_text()
                logging.info(f"Received WS message: {raw_data[:50]}...")
                try:
                    # Handle subscribe for realtime
                    if raw_data.startswith('{"type":"subscribe"'):
                        await self.websocket.send_json({"status": "subscribed", "vault_id": vault_id_str or 'unknown'})
                        continue
                    
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
                    print(f"WS: Exception in message processing loop: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    logging.error(f"WS message processing error: {e} - traceback: {traceback.format_exc()}")
                    await self.websocket.send_json({"status": "error", "error": str(e), "details": traceback.format_exc()})
        
        except WebSocketDisconnect:
            logging.info("WebSocket disconnected: /logs/ws")