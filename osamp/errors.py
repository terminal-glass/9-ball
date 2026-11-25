"""Errors a person can read.

Codes are stable for tests. The plain sentence is what an operator should see.
"""


class OsampError(Exception):
    def __init__(self, code: str, plain: str):
        super().__init__(plain)
        self.code = code
        self.plain = plain
