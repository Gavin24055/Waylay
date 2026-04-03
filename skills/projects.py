"""
J — Project Skills
Task board, git summary, project status tracking.
"""

import logging
import subprocess
from pathlib import Path
from skills.loader import skill

logger = logging.getLogger("j.skills.projects")


def _get_db():
    from memory.structured import StructuredMemory
    return StructuredMemory()


def _get_episodic():
    from memory.episodic import EpisodicMemory
    return EpisodicMemory()


@skill
def project_status(name: str) -> str:
    """Get the status of a project."""
    db = _get_db()
    project = db.get_project(name)
    if not project:
        return f"No project found matching '{name}'."

    tasks = db.get_tasks(project_name=name)
    todo = sum(1 for t in tasks if t["status"] == "todo")
    in_progress = sum(1 for t in tasks if t["status"] == "in_progress")
    done = sum(1 for t in tasks if t["status"] == "done")
    blocked = sum(1 for t in tasks if t["status"] == "blocked")

    lines = [
        f"Project: {project['name']}",
        f"  Stack: {project.get('stack') or 'Not specified'}",
        f"  Status: {project.get('status', 'active')}",
        f"  Tasks: {todo} todo, {in_progress} in progress, {done} done, {blocked} blocked",
    ]
    if project.get("notes"):
        lines.append(f"  Notes: {project['notes']}")

    return "\n".join(lines)


@skill
def log_task(project: str, task: str, status: str = "todo") -> str:
    """Add or update a task for a project."""
    db = _get_db()

    # Ensure project exists
    proj = db.get_project(project)
    if not proj:
        db.save_project(project)
        proj = db.get_project(project)

    task_id = db.add_task(proj["id"], task)
    if status != "todo":
        db.update_task_status(task_id, status)

    # Also save to episodic memory
    try:
        episodic = _get_episodic()
        episodic.save_project_memory(project, f"Task added: {task} (status: {status})")
    except Exception:
        pass

    logger.info("Task logged: %s → %s (%s)", project, task, status)
    return f"Task added to {project}: {task} [{status}]"


@skill
def get_tasks_today() -> str:
    """Get all pending tasks across projects."""
    db = _get_db()
    tasks = db.get_tasks_today()
    if not tasks:
        return "No pending tasks. Clean slate 🎯"

    lines = ["Today's tasks:"]
    for t in tasks:
        priority_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(t["priority"], "⚪")
        project = t.get("project_name") or "General"
        lines.append(f"  {priority_icon} [{project}] {t['title']} ({t['status']})")

    return "\n".join(lines)


@skill
def git_summary(repo_path: str) -> str:
    """Get a git summary for a repository."""
    repo_path = Path(repo_path).expanduser()
    if not (repo_path / ".git").exists():
        return f"Not a git repo: {repo_path}"

    try:
        # Current branch
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_path), capture_output=True, text=True, timeout=5,
        ).stdout.strip()

        # Status summary
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(repo_path), capture_output=True, text=True, timeout=5,
        ).stdout.strip()

        # Recent commits
        log = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            cwd=str(repo_path), capture_output=True, text=True, timeout=5,
        ).stdout.strip()

        # Unpushed commits
        unpushed = subprocess.run(
            ["git", "log", "--oneline", f"origin/{branch}..HEAD"],
            cwd=str(repo_path), capture_output=True, text=True, timeout=5,
        ).stdout.strip()

        lines = [f"Git: {repo_path.name} (branch: {branch})"]

        if status:
            changed = len(status.split("\n"))
            lines.append(f"  Changed files: {changed}")
        else:
            lines.append("  Working tree clean ✨")

        if unpushed:
            count = len(unpushed.split("\n"))
            lines.append(f"  Unpushed commits: {count}")

        lines.append("  Recent commits:")
        for commit_line in log.split("\n")[:5]:
            lines.append(f"    {commit_line}")

        return "\n".join(lines)

    except Exception as e:
        logger.error("Git summary failed: %s", e)
        return f"Git summary failed: {e}"
