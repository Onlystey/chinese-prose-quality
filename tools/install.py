#!/usr/bin/env python3
"""Install one managed skill and a small global instruction block.

Python 3.9+, standard library only. Does not change config.toml, credentials,
models, projects, AGENTS.override.md, or private writing profiles.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
from typing import Dict, Optional
import uuid

NAME = "chinese-prose-quality"
MANIFEST = ".chinese-prose-quality-install.json"
BEGIN = "<!-- BEGIN CHINESE-PROSE-QUALITY -->"
END = "<!-- END CHINESE-PROSE-QUALITY -->"
SCHEMA = 1


class InstallError(Exception):
    """An operation was rejected before removing user-owned content."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def inventory(root: Path, source: bool = False) -> dict:
    files, dirs = {}, []
    for current, names, filenames in os.walk(root, followlinks=False):
        base = Path(current)
        if source:
            names[:] = [n for n in names if n not in {"__pycache__", ".git"}]
        for name in names:
            p = base / name
            if p.is_symlink():
                raise InstallError("Skill directories must not contain symbolic links: " + str(p))
            dirs.append(p.relative_to(root).as_posix())
        for name in filenames:
            p = base / name
            if name == MANIFEST:
                if source:
                    raise InstallError("Source contains reserved installation metadata.")
                continue
            if source and (name == ".DS_Store" or name.endswith((".pyc", ".pyo"))):
                continue
            if p.is_symlink() or not p.is_file():
                raise InstallError("Unexpected non-regular skill file: " + str(p))
            files[p.relative_to(root).as_posix()] = digest(p.read_bytes())
    return {"files": dict(sorted(files.items())), "dirs": sorted(dirs)}


def valid_relative(value: str) -> bool:
    p = PurePosixPath(value)
    return bool(value) and not p.is_absolute() and ".." not in p.parts and str(p) == value


def read_manifest(target: Path) -> dict:
    if target.is_symlink() or not target.is_dir():
        raise InstallError("An unmanaged file or link occupies the skill path: " + str(target))
    path = target / MANIFEST
    if path.is_symlink() or not path.is_file():
        raise InstallError("An unmanaged skill already exists; it will not be overwritten: " + str(target))
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if state["schema"] != SCHEMA or state["name"] != NAME:
            raise ValueError("wrong schema/name")
        inv = state["inventory"]
        if not isinstance(inv["files"], dict) or not isinstance(inv["dirs"], list):
            raise ValueError("bad inventory")
        if not all(valid_relative(k) and isinstance(v, str) and len(v) == 64 for k, v in inv["files"].items()):
            raise ValueError("bad file entry")
        if not all(isinstance(k, str) and valid_relative(k) for k in inv["dirs"]):
            raise ValueError("bad directory entry")
        if not isinstance(state["agents_block"], str) or not isinstance(state["appended_separator"], str):
            raise ValueError("bad guidance metadata")
        if state["appended_separator"] not in ("", "\n", "\n\n"):
            raise ValueError("bad separator")
        if not isinstance(state["agents_existed"], bool):
            raise ValueError("bad AGENTS existence flag")
        if split_block(state["agents_block"])[1] != state["agents_block"]:
            raise ValueError("bad recorded block")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise InstallError("Invalid installation metadata; refusing to overwrite or delete: " + str(path)) from exc
    actual = inventory(target)
    if actual != inv:
        changed = sorted(k for k in set(actual["files"]) | set(inv["files"]) if actual["files"].get(k) != inv["files"].get(k))
        if actual["dirs"] != inv["dirs"]:
            changed.append("[directory layout changed]")
        raise InstallError("Installed skill has changed or added files; preserve/review them before updating or uninstalling: " + ", ".join(changed[:12]))
    return state


def read_agents(path: Path) -> Optional[bytes]:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise InstallError("AGENTS.md is not a regular file; refusing to replace it: " + str(path))
    if not path.exists():
        return None
    data = path.read_bytes()
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InstallError("AGENTS.md must be UTF-8; no changes were made.") from exc
    return data


def split_block(text: str):
    starts, ends = text.count(BEGIN), text.count(END)
    if not starts and not ends:
        return text, None, ""
    if starts != 1 or ends != 1 or text.index(BEGIN) > text.index(END):
        raise InstallError("Duplicate or damaged managed markers in AGENTS.md; refusing to guess boundaries.")
    a, b = text.index(BEGIN), text.index(END) + len(END)
    # Only the block's own newline is managed, never subsequent user content.
    if text[b:b + 1] == "\n":
        b += 1
    return text[:a], text[a:b], text[b:]


def make_block(target: Path, profile: Path) -> str:
    return f"""{BEGIN}
## 中文文字生成与修订

- 当任务涉及中文写作、续写、改写、润色、审稿或校对，包括论文、教材、小说及其他成稿时，先读取并执行 `{target / 'SKILL.md'}`，按文体读取必要参考规范。普通简短问答采用相应强度的语言自检。
- 若本机私有偏好文件 `{profile}` 存在，读取并应用其中与当前任务有关的偏好。它不是公开技能的一部分，不得复制到公开仓库。
- 生成前明确读者、文体、原意与任务范围；交付前逐句检查词义、搭配、主干、修饰范围、指代、关联、否定、数量及标点，再逐段复核逻辑与上下文。区分确定错误、语境待核和风格选择。
- 修改须覆盖本次要求的完整范围，并检查全文同类问题。不得只改用户举例句，不得把未读全文说成已读全文，不得把自动扫描无告警说成没有病句。
- 保留事实、真实引文、术语、人物声音和有意的文学表达。不能由语言规则决定的事实应回查材料，不擅自补造。
- 学术任务同时执行来源与作者性要求；文件编辑同时执行相应格式技能，保留原稿、引用、脚注和批注。
- 通常直接交付已复核成稿；用户要求审计或仍有待核实项时，附必要依据与完成边界，不默认输出冗长检查表。
{END}
"""


def paths(home: Path, codex_home: Path) -> dict:
    return {"target": codex_home / "skills" / NAME, "link": home / ".agents" / "skills" / NAME,
            "agents": codex_home / "AGENTS.md", "profile": codex_home / "writing-profiles" / (NAME + ".md"),
            "override": codex_home / "AGENTS.override.md", "backups": codex_home / "backups" / NAME}


def check_link(link: Path, target: Path, managed: bool):
    if not exists(link):
        return
    if not managed or not link.is_symlink() or link.resolve() != target.resolve():
        raise InstallError("Compatibility skill path is occupied by an unmanaged or conflicting item: " + str(link))


def check_guidance(text: str, state: Optional[dict]):
    before, block, after = split_block(text)
    if block is not None:
        if state is None or block != state["agents_block"]:
            raise InstallError("The managed AGENTS block is unowned or modified; it will not be replaced or deleted.")
    return before, block, after


def atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".cpq-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        if path.exists():
            os.chmod(name, path.stat().st_mode & 0o777)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def backup_agents(root: Path, data: Optional[bytes]) -> Optional[str]:
    if data is None:
        return None
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dest = root / ("AGENTS." + stamp + "." + uuid.uuid4().hex[:8] + ".md")
    with dest.open("xb") as stream:
        stream.write(data)
    return str(dest)


def override_warning(path: Path) -> list:
    if path.is_file() and path.read_bytes().strip():
        return ["A non-empty AGENTS.override.md may supersede AGENTS.md. It was left unchanged; verify the active instruction chain."]
    return []


def restore_agents(path: Path, previous: Optional[bytes]):
    if previous is None:
        if path.exists():
            path.unlink()
    else:
        atomic_write(path, previous)


def install(source: Path, home: Path, codex_home: Path) -> dict:
    p = paths(home, codex_home)
    source = source.resolve()
    if not source.is_dir() or not (source / "SKILL.md").is_file():
        raise InstallError("Source must be a skill directory containing SKILL.md.")
    target = p["target"]
    if source == target.resolve() or source in target.resolve().parents or target.resolve() in source.parents:
        raise InstallError("Source and installation target must be separate, non-nested directories.")
    desired = inventory(source, source=True)
    state = read_manifest(target) if exists(target) else None
    check_link(p["link"], target, state is not None)
    previous = read_agents(p["agents"])
    text = (previous or b"").decode("utf-8")
    before, block, after = check_guidance(text, state)
    new_block = make_block(target, p["profile"])
    separator = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    if block is not None:
        new_text = before + new_block + after
        separator = state["appended_separator"]
    else:
        new_text = text + separator + new_block
    if state and desired == state["inventory"] and new_text == text and exists(p["link"]):
        return {"action": "install", "changed": False, "target": str(target), "warnings": override_warning(p["override"])}
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".cpq-stage-", dir=target.parent))
    old = target.parent / (".cpq-rollback-" + uuid.uuid4().hex)
    moved_old = committed_new = link_created = guidance_written = False
    backup = None
    try:
        for directory in desired["dirs"]:
            (stage / directory).mkdir(parents=True, exist_ok=True)
        for relative in desired["files"]:
            dest = stage / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, dest)
        if inventory(stage) != desired:
            raise InstallError("Source changed during copying; retry after finishing edits.")
        metadata = {"schema": SCHEMA, "name": NAME, "inventory": desired, "agents_block": new_block,
                    "appended_separator": separator,
                    "agents_existed": state["agents_existed"] if state else previous is not None,
                    "installed_at": datetime.now(timezone.utc).isoformat()}
        (stage / MANIFEST).write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if read_agents(p["agents"]) != previous:
            raise InstallError("AGENTS.md changed during preparation; retry without overwriting concurrent edits.")
        if state:
            read_manifest(target)
        check_link(p["link"], target, state is not None)
        backup = backup_agents(p["backups"], previous)
        if state:
            os.replace(target, old)
            moved_old = True
        os.replace(stage, target)
        committed_new = True
        atomic_write(p["agents"], new_text.encode("utf-8"))
        guidance_written = True
        if not exists(p["link"]):
            p["link"].parent.mkdir(parents=True, exist_ok=True)
            p["link"].symlink_to(target, target_is_directory=True)
            link_created = True
    except Exception:
        if link_created:
            p["link"].unlink()
        if guidance_written:
            restore_agents(p["agents"], previous)
        if committed_new:
            shutil.rmtree(target)
        if moved_old:
            os.replace(old, target)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    if moved_old:
        shutil.rmtree(old)
    return {"action": "install", "changed": True, "target": str(target), "compatibility_link": str(p["link"]),
            "agents_backup": backup, "warnings": override_warning(p["override"])}


def uninstall(home: Path, codex_home: Path) -> dict:
    p = paths(home, codex_home)
    previous = read_agents(p["agents"])
    text = (previous or b"").decode("utf-8")
    if not exists(p["target"]):
        if exists(p["link"]) or split_block(text)[1] is not None:
            raise InstallError("Partial/unowned installation remains; refusing to remove items without valid ownership metadata.")
        return {"action": "uninstall", "changed": False}
    state = read_manifest(p["target"])
    check_link(p["link"], p["target"], True)
    before, block, after = check_guidance(text, state)
    if block is None:
        remaining = text
    else:
        sep = state["appended_separator"]
        # If new content follows the managed block, keep the separation so
        # uninstall cannot concatenate the user's preceding/following prose.
        if not after and sep and before.endswith(sep):
            before = before[:-len(sep)]
        remaining = before + after
    if read_agents(p["agents"]) != previous:
        raise InstallError("AGENTS.md changed during preparation; retry.")
    backup = backup_agents(p["backups"], previous)
    holding = p["target"].parent / (".cpq-uninstall-" + uuid.uuid4().hex)
    os.replace(p["target"], holding)
    removed_link = guidance_written = False
    try:
        if exists(p["link"]):
            p["link"].unlink()
            removed_link = True
        if block is not None:
            if remaining:
                atomic_write(p["agents"], remaining.encode("utf-8"))
            elif state["agents_existed"]:
                atomic_write(p["agents"], b"")
            elif p["agents"].exists():
                p["agents"].unlink()
            guidance_written = True
    except Exception:
        os.replace(holding, p["target"])
        if removed_link:
            p["link"].symlink_to(p["target"], target_is_directory=True)
        if guidance_written:
            restore_agents(p["agents"], previous)
        raise
    shutil.rmtree(holding)
    return {"action": "uninstall", "changed": True, "agents_backup": backup,
            "retained": ["unrelated AGENTS.md content", "backups", "private writing profile", "AGENTS.override.md"]}


def status(home: Path, codex_home: Path) -> dict:
    p = paths(home, codex_home)
    result: Dict[str, object] = {"target": str(p["target"]), "compatibility_link": str(p["link"]),
        "agents": str(p["agents"]), "private_profile_exists": p["profile"].is_file(),
        "warnings": override_warning(p["override"])}
    try:
        previous = read_agents(p["agents"])
        text = (previous or b"").decode("utf-8")
        state = read_manifest(p["target"]) if exists(p["target"]) else None
        check_link(p["link"], p["target"], state is not None)
        block = check_guidance(text, state)[1]
        result.update(state="installed" if state else "not_installed", managed_block_present=block is not None,
                      compatibility_link_present=exists(p["link"]))
        if state and (block is None or not exists(p["link"])):
            result["state"] = "incomplete"
    except InstallError as exc:
        result.update(state="conflict_or_modified", detail=str(exc))
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    def options(dest, child=False):
        default = argparse.SUPPRESS if child else None
        dest.add_argument("--home", default=default, help="User home for compatibility skills; when set, default Codex home is HOME/.codex.")
        dest.add_argument("--codex-home", default=default, help="Explicit Codex home; otherwise CODEX_HOME or the selected home/.codex.")
        dest.add_argument("--source", default=default, help="Skill directory to install; defaults to this repository's skills/chinese-prose-quality.")
    options(parser)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("install", "uninstall", "status"):
        options(sub.add_parser(command), child=True)
    args = parser.parse_args(argv)
    home = Path(args.home).expanduser().resolve() if args.home else Path.home().resolve()
    selected_codex = args.codex_home or (None if args.home else os.environ.get("CODEX_HOME"))
    codex_home = Path(selected_codex).expanduser().resolve() if selected_codex else home / ".codex"
    source = Path(args.source).expanduser() if args.source else Path(__file__).resolve().parents[1] / "skills" / NAME
    try:
        result = install(source, home, codex_home) if args.command == "install" else (uninstall(home, codex_home) if args.command == "uninstall" else status(home, codex_home))
    except (InstallError, OSError) as exc:
        print("Refused: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("state") != "conflict_or_modified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
