"""
J — Security Skills
System audit, network connections, process list, CVE digest.
"""

import logging
import psutil
import subprocess
from skills.loader import skill

logger = logging.getLogger("j.skills.security")


@skill
def system_audit() -> str:
    """Run a basic system security audit."""
    findings = []

    # Check for suspicious processes (high CPU/memory)
    suspicious = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            if info["cpu_percent"] and info["cpu_percent"] > 50:
                suspicious.append(f"  ⚠️ {info['name']} (PID {info['pid']}): CPU {info['cpu_percent']:.0f}%")
            if info["memory_percent"] and info["memory_percent"] > 10:
                suspicious.append(f"  ⚠️ {info['name']} (PID {info['pid']}): RAM {info['memory_percent']:.1f}%")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if suspicious:
        findings.append("High resource processes:")
        findings.extend(suspicious[:10])
    else:
        findings.append("✅ No high resource processes detected")

    # Check open network connections
    connections = psutil.net_connections(kind="inet")
    established = [c for c in connections if c.status == "ESTABLISHED"]
    listening = [c for c in connections if c.status == "LISTEN"]
    findings.append(f"\nNetwork: {len(established)} established, {len(listening)} listening")

    # Check for unusual listening ports (above 1024 that aren't common)
    common_ports = {3000, 3306, 5432, 5000, 8000, 8080, 8443, 11434, 27017}
    unusual = [c for c in listening if c.laddr.port > 1024 and c.laddr.port not in common_ports]
    if unusual:
        findings.append("  Unusual listening ports:")
        for c in unusual[:5]:
            pid_name = ""
            if c.pid:
                try:
                    pid_name = psutil.Process(c.pid).name()
                except Exception:
                    pass
            findings.append(f"    Port {c.laddr.port} ({pid_name or 'unknown'})")

    # Login activity (macOS)
    try:
        result = subprocess.run(["last", "-10"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            findings.append(f"\nRecent logins (last 10):")
            for line in result.stdout.strip().split("\n")[:5]:
                findings.append(f"  {line.strip()}")
    except Exception:
        pass

    return "\n".join(findings)


@skill
def network_connections() -> str:
    """List active network connections."""
    try:
        connections = psutil.net_connections(kind="inet")
        established = [c for c in connections if c.status == "ESTABLISHED"]

        if not established:
            return "No active network connections."

        lines = [f"Active connections ({len(established)}):"]
        for c in established[:20]:
            local = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "?"
            remote = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "?"
            pid_name = ""
            if c.pid:
                try:
                    pid_name = psutil.Process(c.pid).name()
                except Exception:
                    pid_name = f"PID {c.pid}"
            lines.append(f"  {local} → {remote} [{pid_name}]")

        return "\n".join(lines)
    except Exception as e:
        return f"Network info failed: {e}"


@skill
def process_list() -> str:
    """List top processes by CPU and memory usage."""
    procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # Sort by CPU usage descending
    procs.sort(key=lambda p: p.get("cpu_percent", 0) or 0, reverse=True)

    lines = ["Top processes by CPU:"]
    for p in procs[:15]:
        cpu = p.get("cpu_percent", 0) or 0
        mem = p.get("memory_percent", 0) or 0
        lines.append(f"  {p['name']:<30} CPU: {cpu:5.1f}%  RAM: {mem:5.1f}%  PID: {p['pid']}")

    return "\n".join(lines)


@skill
def cve_digest() -> str:
    """Get recent CVE/security news headlines."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.news("CVE vulnerability security latest", max_results=5))

        if not results:
            return "No recent security news found."

        lines = ["Recent security/CVE news:"]
        for r in results:
            lines.append(f"  🔒 {r['title']}")
            lines.append(f"     {r.get('body', '')[:120]}")
        return "\n".join(lines)
    except Exception as e:
        return f"Security news fetch failed: {e}"
