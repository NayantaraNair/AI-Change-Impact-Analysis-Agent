"""Index source files with simple, language-aware regexes: classes, functions,
API routes and database tables. Deterministic; nothing is executed.
"""

from __future__ import annotations

import re
from collections import defaultdict

from app.contracts import CodeFile, CodeService, RepoIndex

LANGUAGES = {
    ".py": "python", ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".ts": "typescript",
    ".tsx": "typescript", ".js": "javascript", ".jsx": "javascript", ".go": "go", ".cs": "csharp",
    ".rb": "ruby", ".php": "php", ".scala": "scala", ".sql": "sql", ".prisma": "prisma",
}
# Folders whose children are separate services or apps.
SERVICE_PARENTS = {"services", "apps", "packages", "modules", "microservices", "components"}

_HTTP = r"(get|post|put|patch|delete)"
_CLASS = {
    "python": re.compile(r"^\s*class\s+([A-Za-z_]\w*)", re.M),
    "go": re.compile(r"^type\s+([A-Za-z_]\w*)\s+(?:struct|interface)\b", re.M),
    "sql": None,
    "prisma": re.compile(r"^model\s+(\w+)\s*\{", re.M),
}
_CLASS_DEFAULT = re.compile(r"\b(?:class|interface|enum|record|object|struct)\s+([A-Z]\w*)")
_FUNC = {
    "python": re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)", re.M),
    "go": re.compile(r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)", re.M),
    "typescript": re.compile(r"(?:function\s+([A-Za-z_]\w*)|^\s+(?:async\s+)?([a-z]\w*)\s*\([^)]*\)\s*(?::[^{]+)?\{)", re.M),
    "javascript": re.compile(r"(?:function\s+([A-Za-z_]\w*)|^\s+(?:async\s+)?([a-z]\w*)\s*\([^)]*\)\s*\{)", re.M),
    "java": re.compile(r"^\s+(?:public|protected|private)[\w<>\[\],\s]*\s([a-z]\w*)\s*\(", re.M),
    "kotlin": re.compile(r"\bfun\s+([a-z]\w*)\s*\(", re.M),
    "csharp": re.compile(r"^\s+(?:public|protected|private|internal)[\w<>\[\],\s]*\s([A-Z]\w*)\s*\(", re.M),
}
_API = [
    # FastAPI / Flask-style decorators: @router.post("/x"), @app.get("/x")
    (re.compile(rf"@\w+(?:\.\w+)*\.{_HTTP}\(\s*[\"']([^\"']+)", re.I), None),
    # Express / Koa / Gin: router.get('/x'), app.post("/x"), r.GET("/x"). Only route
    # objects, so outgoing calls like client.post("/notify/sms") are not counted.
    (re.compile(rf"\b(?:router|app|api|server|routes|route|r|e|g|group|engine)\.{_HTTP}\(\s*[\"'`](/[^\"'`]*)", re.I), None),
    # Spring: @GetMapping("/x"), @PostMapping(value = "/x")
    (re.compile(r"@(Get|Post|Put|Patch|Delete)Mapping\(\s*(?:value\s*=\s*|path\s*=\s*)?\"([^\"]+)\""), None),
    # Go net/http: HandleFunc("/x", ...)
    (re.compile(r"HandleFunc\(\s*\"([^\"]+)\""), "ANY"),
    # Flask: @app.route("/x")
    (re.compile(r"@\w+\.route\(\s*[\"']([^\"']+)"), "ANY"),
]
_TABLES = [
    re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`\[]?(\w+)", re.I),
    re.compile(r"ALTER\s+TABLE\s+[\"`\[]?(\w+)", re.I),
    re.compile(r"__tablename__\s*=\s*[\"'](\w+)"),
    re.compile(r"@Table\(\s*name\s*=\s*\"(\w+)\""),
    re.compile(r"@Entity\(\s*[\"'](\w+)[\"']"),
    re.compile(r"\bmodel\(\s*[\"'](\w+)[\"']"),
]
_PREFIX = re.compile(r"@RequestMapping\(\s*(?:value\s*=\s*|path\s*=\s*)?\"([^\"]+)\"")


def _unique(items, limit: int) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))[:limit]


def service_of(path: str) -> str:
    parts = path.split("/")
    for index, part in enumerate(parts[:-1]):
        if part.lower() in SERVICE_PARENTS and index + 1 < len(parts) - 1:
            return parts[index + 1]
    if len(parts) > 1:
        top = parts[0]
        return "database" if top.lower() in {"db", "database", "migrations", "sql"} else top
    return "root"


def index_file(path: str, text: str) -> CodeFile | None:
    language = LANGUAGES.get(path[path.rfind("."):].lower()) if "." in path else None
    if language is None:
        return None
    class_pattern = _CLASS.get(language, _CLASS_DEFAULT)
    classes = _unique(class_pattern.findall(text), 40) if class_pattern else []
    func_pattern = _FUNC.get(language)
    functions = []
    if func_pattern:
        for match in func_pattern.findall(text):
            name = match if isinstance(match, str) else next((item for item in match if item), "")
            if name and name not in {"if", "for", "while", "switch", "catch", "return", "constructor"}:
                functions.append(name)
    prefix = (_PREFIX.search(text)[1].rstrip("/") if _PREFIX.search(text) else "")
    apis = []
    for pattern, method in _API:
        for match in pattern.findall(text):
            if method:
                verb, route = method, match
            else:
                verb, route = match[0].upper(), match[1]
            if not route.startswith("/"):
                continue
            if "Mapping" in pattern.pattern and prefix and not route.startswith(prefix):
                route = prefix + route
            apis.append(f"{verb} {route}")
    tables = []
    for pattern in _TABLES:
        tables.extend(match.lower() for match in pattern.findall(text))
    return CodeFile(
        path=path, service=service_of(path), language=language, classes=classes,
        functions=_unique(functions, 30), apis=_unique(apis, 30), tables=_unique(tables, 30),
    )


def build_index(repo_url: str, ref: str, root: str, tree: list[str], texts: dict[str, str], truncated: bool) -> RepoIndex:
    files = [indexed for path in tree if path in texts and (indexed := index_file(path, texts[path]))]
    grouped: dict[str, list[CodeFile]] = defaultdict(list)
    for file in files:
        grouped[file.service].append(file)
    services = []
    for name, members in sorted(grouped.items()):
        first = members[0].path.split("/")
        depth = next((i + 2 for i, part in enumerate(first[:-1]) if part.lower() in SERVICE_PARENTS), 1)
        services.append(CodeService(
            name=name, path="/".join(first[:depth]) if name != "root" else "",
            languages=sorted({file.language for file in members}),
            files=len(members),
            classes=sum(len(file.classes) for file in members),
            apis=sum(len(file.apis) for file in members),
            tables=_unique((table for file in members for table in file.tables), 40),
        ))
    return RepoIndex(repo_url=repo_url, ref=ref, root=root, tree=tree, files=files, services=services, truncated=truncated)
