"""Eventos determinísticos: não incluem relógio nem diretórios transitórios."""


class Audit:
    def __init__(self):
        self.events = []

    def add(self, code, message, *, severity="info", **context):
        event = {"event_id": f"event_{len(self.events) + 1:06}", "code": code,
                 "severity": severity, "message": message, **context}
        self.events.append(event)
        return event["event_id"]
