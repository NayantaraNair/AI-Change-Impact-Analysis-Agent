"""Download a public GitHub repository as an archive and read its files in memory.

Nothing is executed and nothing is unpacked to disk: the tarball is streamed
with a size cap and read member by member. A `/tree/<ref>/<folder>` URL limits
the analysis to that folder.
"""

from __future__ import annotations

import io
import re
import tarfile
from dataclasses import dataclass
from pathlib import Path

import httpx

from app import config

MAX_ARCHIVE_BYTES = 80 * 1024 * 1024
MAX_FILE_BYTES = 200 * 1024
MAX_TREE = 5000
TIMEOUT_S = 60

# This project's own repository is read from the local checkout when present,
# so the bundled demo (examples/demo-bank) works offline and before it is pushed.
LOCAL_MIRRORS = {"nayantaranair/ai-change-impact-analysis-agent": config.REPO_ROOT}

_URL = re.compile(
    r"^https?://(?:www\.)?github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?"
    r"(?:/tree/(?P<ref>[\w.-]+)(?:/(?P<path>[^?#]*))?)?/?(?:[?#].*)?$"
)
SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "target", "vendor", "__pycache__", ".venv",
    "venv", ".next", "coverage", ".idea", ".gradle", "bin", "obj",
}


class RepoError(ValueError):
    """The URL or repository can't be analysed; the message is shown to the user."""


@dataclass(frozen=True)
class RepoRef:
    owner: str
    repo: str
    ref: str
    path: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}".lower()


@dataclass
class RepoFiles:
    ref: RepoRef
    tree: list[str]
    texts: dict[str, str]
    truncated: bool


def parse_url(url: str) -> RepoRef:
    match = _URL.match(url.strip())
    if not match:
        raise RepoError("Use a public GitHub URL, like https://github.com/owner/repo or https://github.com/owner/repo/tree/main/folder.")
    path = (match["path"] or "").strip("/")
    if ".." in path.split("/"):
        raise RepoError("The folder path can't contain '..'.")
    return RepoRef(match["owner"], match["repo"], match["ref"] or "HEAD", path)


def _wanted(path: str) -> bool:
    return not any(part in SKIP_DIRS or part.startswith(".") for part in path.split("/")[:-1])


def _read_local(ref: RepoRef, root: Path) -> RepoFiles:
    base = (root / ref.path).resolve()
    if not base.is_dir() or not base.is_relative_to(root.resolve()):
        raise RepoError(f"The folder '{ref.path}' doesn't exist in this repository.")
    tree, texts, truncated = [], {}, False
    for file in sorted(base.rglob("*")):
        rel = file.relative_to(base).as_posix()
        if not file.is_file() or not _wanted(rel):
            continue
        if len(tree) >= MAX_TREE:
            truncated = True
            break
        tree.append(rel)
        if file.stat().st_size <= MAX_FILE_BYTES:
            try:
                texts[rel] = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                pass
    return RepoFiles(ref, tree, texts, truncated)


def _read_archive(ref: RepoRef, payload: bytes) -> RepoFiles:
    tree, texts, truncated = [], {}, False
    prefix = f"{ref.path}/" if ref.path else ""
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive:
            if not member.isfile():
                continue
            # Archives wrap everything in "<repo>-<ref>/"; drop it.
            full = member.name.split("/", 1)[1] if "/" in member.name else ""
            if not full.startswith(prefix) or not full[len(prefix):]:
                continue
            rel = full[len(prefix):]
            if not _wanted(rel):
                continue
            if len(tree) >= MAX_TREE:
                truncated = True
                break
            tree.append(rel)
            if member.size <= MAX_FILE_BYTES:
                handle = archive.extractfile(member)
                if handle is not None:
                    try:
                        texts[rel] = handle.read().decode("utf-8")
                    except UnicodeDecodeError:
                        pass
    if not tree:
        raise RepoError(f"No files found{f' under {ref.path}' if ref.path else ''}. Check the URL and branch.")
    return RepoFiles(ref, sorted(tree), texts, truncated)


async def fetch_repo(url: str) -> RepoFiles:
    ref = parse_url(url)
    local = LOCAL_MIRRORS.get(ref.slug)
    if local is not None and (Path(local) / ref.path).is_dir():
        return _read_local(ref, Path(local))
    archive_url = f"https://github.com/{ref.owner}/{ref.repo}/archive/{ref.ref}.tar.gz"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S, follow_redirects=True) as client:
            async with client.stream("GET", archive_url) as response:
                if response.status_code == 404:
                    raise RepoError("Repository or branch not found. It must be public on GitHub.")
                if response.status_code >= 400:
                    raise RepoError(f"GitHub returned {response.status_code} for this repository.")
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_ARCHIVE_BYTES:
                        raise RepoError("This repository is over 80 MB. Point the URL at a smaller folder with /tree/<branch>/<folder>.")
                    chunks.append(chunk)
    except httpx.HTTPError as exc:
        raise RepoError(f"Couldn't download the repository from GitHub ({type(exc).__name__}).") from None
    try:
        return _read_archive(ref, b"".join(chunks))
    except tarfile.TarError:
        raise RepoError("GitHub didn't return a readable archive for this repository.") from None
