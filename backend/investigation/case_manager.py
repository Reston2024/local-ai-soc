"""Case manager stub — Phase 7 Plan 01 will implement."""


class CaseManager:
    def create_investigation_case(self, sqlite_conn, title: str, description: str = "", case_id=None) -> str:
        raise NotImplementedError

    def get_investigation_case(self, sqlite_conn, case_id: str) -> dict | None:
        raise NotImplementedError

    def list_investigation_cases(self, sqlite_conn, status=None) -> list:
        raise NotImplementedError

    def update_investigation_case(self, sqlite_conn, case_id: str, updates: dict) -> None:
        raise NotImplementedError
