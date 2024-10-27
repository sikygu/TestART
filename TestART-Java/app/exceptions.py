from app.constants import ExceptionCode
class ApiException(Exception):
    def __init__(self, exception_code: ExceptionCode, error_msg: str, error=None, code: int = 500):
        self.error_code: ExceptionCode = exception_code
        self.error_msg: str = error_msg
        self.code: int = code
        self.error = None

    def dict(self):
        return {
            "data" : None,
            "error_code": self.error_code,
            "error_msg": self.error_msg,
        }
