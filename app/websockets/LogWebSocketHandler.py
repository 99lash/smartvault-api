from fastapi import WebSocket, WebSocketDisconnect
from app.schemas.log import LogCreate
from app.services.logs.LogService import LogService
from app.services.logs.AuthHandlerService import AuthHandlerService
from app.services.logs.VaultAccessControllerService import VaultAccessController
from app.services.logs.LogQueryService import LogQueryService
from app.services.logs.BruteforceDetectionService import BruteforceDetectionService
from app.services.users.UserService import UserService
from app.repositories.VaultMembershipRepository import VaultMembershipRepository
from app.models.Log import LogEventType
from app.core.database import get_db_manual
import logging
import json

class LogWebSocketHandler:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.db_sessions = []  # ✅ Track all DB sessions for cleanup

    def _get_redis_services(self):
        """Get Redis services from the app state"""
        try:
            from app.main import app
            return (
                app.state.redis_client,
                app.state.bruteforce_service,
                app.state.event_manager
            )
        except Exception:
            return None, None, None
    
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
        logging.info(f"Cleaning up WebSocket handler - {len(self.db_sessions)} sessions to close")
        for db in self.db_sessions[:]:  # Use slice to avoid modification during iteration
            try:
                db.close()
                logging.info("DB session closed")
            except Exception as e:
                logging.error(f"Error closing DB session during cleanup: {e}")
        self.db_sessions.clear()
        logging.info("WebSocket handler cleanup complete")

    async def handle_connection(self):
        """
        Main handler for /logs/ws connections.
        Accepts, loops for messages, dispatches events.
        Supports query mode if prefixes param present (for log retrieval with auth).
        """
        logging.info(f"WS connection attempt from {self.websocket.client.host}")
        await self.websocket.accept()
        logging.info("WS connection accepted")
        
        # Check for query mode (log retrieval with auth)
        query_params = self.websocket.query_params
        token = query_params.get('token')
        vault_id_str = str(query_params.get('vault_id'))
        prefixes_str = query_params.get('prefixes', '')
        
        logging.info(f"Query params: token present={bool(token)}, vault_id={vault_id_str}, prefixes={prefixes_str[:50]}")
        
        if prefixes_str and token and vault_id_str:
            logging.info("Detected query mode")
            db = None  # ✅ Initialize to None for proper cleanup
            try:
                vault_id = vault_id_str
                prefixes = [p.strip() for p in prefixes_str.split(',') if p.strip()]
                
                # ✅ Create tracked DB session
                db = self._create_db_session()
                
                # Validate token and get user
                try:
                    logging.info(f"Validating token for vault {vault_id}")
                    user = UserService.validate_token(token, db)
                    logging.info(f"Token validated for user {user.username}, id={user.id}")
                except ValueError as auth_err:
                    logging.warning(f"WS auth failed for vault {vault_id}: {auth_err}")
                    await self.websocket.send_json({
                        "status": "error", 
                        "message": "Invalid token", 
                        "details": str(auth_err)
                    })
                    await self.websocket.close(code=1008)  # Policy violation
                    return  # cleanup() will be called by route handler
                except Exception as general_err:
                    logging.error(f"WS token validation error: {general_err}")
                    await self.websocket.send_json({
                        "status": "error", 
                        "message": "Token validation error", 
                        "details": str(general_err)
                    })
                    await self.websocket.close(code=1008)
                    return
                
                # Check vault access
                logging.info(f"Checking vault access for user {user.id}, vault {vault_id}")
                vault_membership_repo = VaultMembershipRepository(db)
                controller = VaultAccessController(vault_membership_repo)
                
                if not controller.check_access(user.id, vault_id):
                    logging.warning(f"User {user.username} denied access to vault {vault_id}")
                    await self.websocket.send_json({
                        "status": "error", 
                        "message": "No access to vault", 
                        "vault_id": vault_id, 
                        "user_id": user.id
                    })
                    await self.websocket.close(code=1008)
                    return
                
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
                logging.info(f"Query successful, sent {len(logs)} logs")
                
                # ✅ Close the query session immediately after use
                self._close_db_session(db)
                db = None  # Mark as closed
                
            except ValueError as ve:
                logging.error(f"WS query param error: {ve}")
                await self.websocket.send_json({
                    "status": "error", 
                    "message": "Invalid vault_id or prefixes", 
                    "details": str(ve)
                })
            except Exception as e:
                logging.error(f"WS query error: {e}")
                import traceback
                await self.websocket.send_json({
                    "status": "error", 
                    "error": str(e), 
                    "traceback": traceback.format_exc()
                })
            finally:
                # ✅ Ensure session is closed even on error
                if db is not None:
                    self._close_db_session(db)
        
        # Normal event handling (or continue after query)
        try:
            while True:
                raw_data = await self.websocket.receive_text()
                logging.info(f"Received WS message: {raw_data[:50]}...")
                
                # ✅ Create a NEW session for EACH message
                db = self._create_db_session()
                
                try:
                    # Handle subscribe for realtime
                    if raw_data.startswith('{"type":"subscribe"'):
                        await self.websocket.send_json({
                            "status": "subscribed", 
                            "vault_id": vault_id_str or 'unknown'
                        })
                        continue
                    
                    payload = LogCreate.model_validate_json(raw_data)
                    service = LogService(db)
                    auth_handler = AuthHandlerService(service)
                    
                    if payload.event_type == LogEventType.unlock and payload.details:
                        response = auth_handler.handle_unlock_request(payload)
                        db.commit()  # ✅ Explicit commit
                        await self.websocket.send_json(response)
                    
                    elif payload.event_type == LogEventType.failed_attempt and payload.details:
                        vault_id = service._get_vault_id_by_device_id(payload.device_id)

                        # Use Redis-based bruteforce detection if available
                        redis_client, bruteforce_service, event_manager = self._get_redis_services()
                        tamper_detected = False

                        if bruteforce_service and redis_client:
                            try:
                                # Check for bruteforce using Redis
                                method = "nfc" if "NFC" in payload.details else "pin"
                                tamper_detected = bruteforce_service.check_threshold_and_log_tamper(
                                    vault_id, method
                                )
                                logging.info(f"Bruteforce check for vault {vault_id}, method {method}: {'TAMPER' if tamper_detected else 'OK'}")
                            except Exception as e:
                                logging.error(f"Bruteforce detection error: {e}")
                                tamper_detected = False

                        new_log = service.log_failed_unlock_attempt(
                            device_id=payload.device_id,
                            user_id=None,
                            reason=payload.details
                        )
                        service.clear_sessions_for_vault(payload.device_id)
                        db.commit()  # ✅ Explicit commit

                        # Broadcast to Redis if event manager is available
                        if event_manager and new_log:
                            try:
                                await event_manager._broadcast_to_vault(vault_id, {
                                    "id": new_log.id,
                                    "device_id": new_log.device_id,
                                    "event_type": new_log.event_type.value,
                                    "details": new_log.details,
                                    "created_at": new_log.created_at.isoformat(),
                                    "tamper_detected": tamper_detected
                                })
                            except Exception as e:
                                logging.error(f"Event broadcast error: {e}")

                        await self.websocket.send_json({
                            "status": "ok",
                            "event_type": "failed_attempt",
                            "tamper_detected": tamper_detected
                        })
                    
                    elif payload.event_type == LogEventType.tamper and payload.details:
                        new_log = service.log_tamper_detection(
                            device_id=payload.device_id,
                            sensor_data=payload.details
                        )
                        service.clear_sessions_for_vault(payload.device_id)
                        db.commit()  # ✅ Explicit commit
                        await self.websocket.send_json({
                            "status": "ok", 
                            "event_type": "tamper"
                        })
                    
                    else:
                        new_log = service.create_log(
                            device_id=payload.device_id,
                            event_type=payload.event_type,
                            user_id=None,
                            details=payload.details,
                        )
                        db.commit()  # ✅ Explicit commit

                        if new_log:
                            # Broadcast to Redis if event manager is available
                            redis_client, bruteforce_service, event_manager = self._get_redis_services()
                            if event_manager:
                                try:
                                    vault_id = service._get_vault_id_by_device_id(payload.device_id)
                                    await event_manager._broadcast_to_vault(vault_id, {
                                        "id": new_log.id,
                                        "device_id": new_log.device_id,
                                        "event_type": new_log.event_type.value,
                                        "details": new_log.details,
                                        "created_at": new_log.created_at.isoformat()
                                    })
                                except Exception as e:
                                    logging.error(f"Event broadcast error: {e}")

                            await self.websocket.send_json({
                                "status": "ok",
                                "event_type": new_log.event_type.value
                            })
                        else:
                            await self.websocket.send_json({
                                "status": "error",
                                "message": "Invalid event_type or details"
                            })
                
                except Exception as e:
                    logging.error(f"WS message processing error: {e}")
                    db.rollback()  # ✅ Rollback on error
                    import traceback
                    await self.websocket.send_json({
                        "status": "error", 
                        "error": str(e), 
                        "details": traceback.format_exc()
                    })
                finally:
                    # ✅ CRITICAL: Close session after EACH message
                    self._close_db_session(db)
        
        except WebSocketDisconnect:
            logging.info("WebSocket disconnected: /logs/ws")
        except Exception as e:
            logging.error(f"WebSocket error: {e}")