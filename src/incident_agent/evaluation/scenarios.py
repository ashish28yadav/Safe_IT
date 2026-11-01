"""Fixed evaluation inputs and expected diagnosis/action outcomes."""

SCENARIOS = [
    {"name": "payment_errors", "title": "Payment provider errors", "description": "Payment requests time out at the gateway", "service": "payment", "scenario": "payment_errors", "expected_action": "restart_service"},
    {"name": "authentication_timeout", "title": "Authentication requests timing out", "description": "Token validation requests are slow", "service": "authentication", "scenario": "authentication_timeout", "expected_action": "restart_service"},
    {"name": "notification_backlog", "title": "Notification queue growing", "description": "Queue depth is elevated and delivery is delayed", "service": "notification", "scenario": "notification_backlog", "expected_action": "clear_notification_backlog"},
    {"name": "database_connection_exhaustion", "title": "Database connections exhausted", "description": "PostgreSQL rejects new pooled connections", "service": "postgres", "scenario": "database_connection_exhaustion", "expected_action": "recycle_db_connections"},
]
