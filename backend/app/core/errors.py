import uuid
import logging
from django.db import OperationalError, InterfaceError
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response


class DomainError(APIException):
    def __init__(self, code, message=None, status=409, retryable=False, task_id=None):
        self.status_code = status
        self.payload = {"code": code, "message": message or code.replace("_", " ").capitalize(),
                        "field_errors": {}, "retryable": retryable, "diagnostic_id": str(uuid.uuid4())}
        if task_id:
            self.payload["task_id"] = str(task_id)
        super().__init__(code)


def exception_handler(exc, context):
    if isinstance(exc,(OperationalError,InterfaceError)):
        # The database may be down, so diagnostics must not depend on another DB write.
        # Driver messages can contain credentials or SQL/source text; log a safe identifier only.
        diagnostic_id=str(uuid.uuid4())
        request=context.get("request")
        logging.getLogger("app.diagnostics").error("DATABASE_UNAVAILABLE diagnostic_id=%s operation=%s",
            diagnostic_id,getattr(request,"method","unknown"))
        return Response({"code":"DATABASE_UNAVAILABLE","message":"The local database is temporarily unavailable. Your edits are kept. Retry after reconnecting.",
            "field_errors":{},"retryable":True,"diagnostic_id":diagnostic_id},status=503)
    if isinstance(exc, DomainError):
        return Response(exc.payload, status=exc.status_code)
    response = drf_exception_handler(exc, context)
    if response is not None:
        response.data = {
            "code": getattr(exc, "default_code", "REQUEST_ERROR"),
            "message": str(getattr(exc, "detail", "Request could not be completed")),
            "field_errors": response.data if isinstance(response.data, dict) else {},
            "retryable": False, "diagnostic_id": str(uuid.uuid4()),
        }
    return response
