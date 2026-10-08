"""Codebase impact: URL parsing, indexing, the story -> code mapping and its guards."""

import pytest
from fastapi.testclient import TestClient

from app import llm
from app.api.main import app
from app.codebase import pipeline
from app.codebase.agent import MAX_TESTS, MIN_TESTS
from app.codebase.fetch import RepoError, RepoFiles, parse_url
from app.codebase.index import build_index, index_file, service_of
from app.contracts import CodebaseRequest, StoryInput

REPO = {
    "services/auth-service/app/main.py": '''
from fastapi import APIRouter
router = APIRouter()

@router.post("/auth/login")
async def login(): ...

@router.post("/auth/token/refresh")
async def refresh(): ...
''',
    "services/auth-service/app/auth/session.py": "class SessionManager:\n    def issue(self): ...\n\nclass TokenIssuer:\n    pass\n",
    "services/auth-service/app/models.py": 'class User(Base):\n    __tablename__ = "users"\n\nclass LoginAttempt(Base):\n    __tablename__ = "login_attempts"\n',
    "services/auth-service/app/clients/notification.py": 'class NotificationClient:\n    async def send_sms(self):\n        await self.client.post("/notify/sms")\n',
    "services/payment-service/src/main/java/com/bank/PaymentController.java": '''
@RestController
@RequestMapping("/v1")
public class PaymentController {
    @PostMapping("/payments")
    public Payment create() { return null; }
}
''',
    "services/payment-service/src/main/java/com/bank/Payment.java": '@Entity\n@Table(name = "payments")\npublic class Payment {}\n',
    "services/customer-service/src/routes/customers.ts": "router.get('/customers/:id', handler);\nexport class ProfileService {}\n",
    "services/notification-service/cmd/server/main.go": 'package main\nfunc main() {\n  http.HandleFunc("/notify/sms", sms)\n}\ntype SmsSender struct {}\n',
    "db/migrations/001_users.sql": "CREATE TABLE users (id int);\nCREATE TABLE IF NOT EXISTS login_attempts (id int);\n",
    "README.md": "# Bank\n",
}
OTP = StoryInput(
    id="EX-1", title="OTP multi-factor login",
    description="After the password is accepted, send a one-time passcode by SMS and verify it before issuing a session token.",
    acceptance_criteria=["A session is issued only after a valid OTP.", "Five failed codes lock the login."],
)
URL = "https://github.com/acme/bank/tree/main/services"


def test_parse_url_variants_and_errors():
    assert parse_url("https://github.com/acme/bank").ref == "HEAD"
    ref = parse_url("https://github.com/acme/bank.git/tree/dev/services/auth")
    assert (ref.owner, ref.repo, ref.ref, ref.path) == ("acme", "bank", "dev", "services/auth")
    for bad in ["https://gitlab.com/acme/bank", "not a url", "https://github.com/acme/bank/tree/main/../etc"]:
        with pytest.raises(RepoError):
            parse_url(bad)


def test_index_extracts_classes_routes_and_tables_per_language():
    auth = index_file("services/auth-service/app/main.py", REPO["services/auth-service/app/main.py"])
    assert auth.service == "auth-service" and auth.apis == ["POST /auth/login", "POST /auth/token/refresh"]
    models = index_file("services/auth-service/app/models.py", REPO["services/auth-service/app/models.py"])
    assert models.classes == ["User", "LoginAttempt"] and models.tables == ["users", "login_attempts"]
    client = index_file("services/auth-service/app/clients/notification.py", REPO["services/auth-service/app/clients/notification.py"])
    assert client.apis == []  # an outgoing call is not the service's own route
    java = index_file("services/payment-service/src/main/java/com/bank/PaymentController.java", REPO["services/payment-service/src/main/java/com/bank/PaymentController.java"])
    assert java.apis == ["POST /v1/payments"] and "PaymentController" in java.classes
    go = index_file("services/notification-service/cmd/server/main.go", REPO["services/notification-service/cmd/server/main.go"])
    assert go.apis == ["ANY /notify/sms"] and go.classes == ["SmsSender"]
    sql = index_file("db/migrations/001_users.sql", REPO["db/migrations/001_users.sql"])
    assert sql.service == "database" and sql.tables == ["users", "login_attempts"]
    assert index_file("README.md", "# x") is None


def test_service_grouping():
    assert service_of("services/auth-service/app/main.py") == "auth-service"
    assert service_of("apps/web/src/index.ts") == "web"
    assert service_of("lib/util.py") == "lib"
    assert service_of("main.py") == "root"


@pytest.fixture
def fake_repo(monkeypatch):
    monkeypatch.setattr(pipeline, "_indexes", {})

    async def fetch(url):
        return RepoFiles(parse_url(url), sorted(REPO), dict(REPO), False)

    monkeypatch.setattr(pipeline, "fetch_repo", fetch)


async def test_keyword_flow_maps_otp_story_to_auth_and_plans_tests(fake_repo):
    result = await pipeline.analyze_codebase(CodebaseRequest(repo_url=URL, story=OTP))
    services = [impact.service for impact in result.services]
    assert services[0] == "auth-service" and "payment-service" not in services
    paths = {file.path for file in result.files}
    assert paths <= set(REPO) and any("session.py" in path for path in paths)
    auth = result.services[0]
    assert "SessionManager" in auth.classes or "LoginAttempt" in auth.classes
    assert MIN_TESTS <= len(result.tests) <= MAX_TESTS
    assert {test.category for test in result.tests} <= {"functional", "api", "integration", "unit", "regression", "security"}
    assert "security" in {test.category for test in result.tests}
    assert result.providers_used["map_services"] == "keyword-fallback"
    assert set(result.repo.tree) == set(REPO)


async def test_model_choices_are_validated_against_the_index(fake_repo, monkeypatch):
    calls = []

    async def complete(system, user, schema, tier="fast", max_tokens=0):
        calls.append(schema.__name__)
        if schema.__name__ == "_Services":
            return schema(services=[{"name": "auth-service", "reason": "login"}, {"name": "invented-service", "reason": "x"}]), "mock:m"
        if schema.__name__ == "_Files":
            return schema(files=[
                {"path": "services/auth-service/app/auth/session.py", "reason": "sessions", "classes": ["SessionManager", "Ghost"]},
                {"path": "services/nowhere.py", "reason": "x", "classes": []},
            ]), "mock:m"
        return schema(tests=[{"title": "One test", "category": "unit", "target": "SessionManager", "steps": ["do"], "expected": "ok"}]), "mock:m"

    monkeypatch.setattr(llm, "complete_structured", complete)
    result = await pipeline.analyze_codebase(CodebaseRequest(repo_url=URL, story=OTP))
    assert [impact.service for impact in result.services] == ["auth-service"]
    assert [file.path for file in result.files] == ["services/auth-service/app/auth/session.py"]
    assert result.files[0].classes == ["SessionManager"]
    assert len(result.tests) == MIN_TESTS  # topped up from templates
    assert calls == ["_Services", "_Files", "_Tests"]


def test_api_rejects_bad_urls_and_runs_codebase(fake_repo, monkeypatch):
    with TestClient(app) as client:
        bad = client.post("/runs/codebase", json={"repo_url": "https://example.com/x", "story": OTP.model_dump()})
        assert bad.status_code == 422 and "GitHub" in bad.json()["detail"]
        ok = client.post("/codebase/analyze", json={"repo_url": URL, "story": OTP.model_dump()})
        assert ok.status_code == 200, ok.text
        assert ok.json()["services"][0]["service"] == "auth-service"
