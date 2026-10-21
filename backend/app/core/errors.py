import uuid
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
