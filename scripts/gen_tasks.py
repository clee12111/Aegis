#!/usr/bin/env python3
"""Generate the full TASKS list with oracle metadata from BountyBench."""
import json, glob, os

bb = "/home/ppeng/bountybench"

for task_dir in sorted(glob.glob(os.path.join(bb, "bountytasks", "*"))):
    system = os.path.basename(task_dir)
    if system.startswith(".") or not os.path.isdir(task_dir):
        continue
    meta_path = os.path.join(task_dir, "metadata.json")
    if not os.path.exists(meta_path):
        continue

    has_docker = os.path.exists(os.path.join(task_dir, "docker-compose.yml"))
    setup_sh = os.path.join(task_dir, "setup_repo_env.sh")
    if os.path.exists(setup_sh):
        if "docker" in open(setup_sh).read().lower():
            has_docker = True

    bounties_dir = os.path.join(task_dir, "bounties")
    if not os.path.isdir(bounties_dir):
        continue

    for bounty_dir in sorted(glob.glob(os.path.join(bounties_dir, "bounty_*"))):
        bounty_num = os.path.basename(bounty_dir).split("_")[1]
        bmeta_path = os.path.join(bounty_dir, "bounty_metadata.json")
        if not os.path.exists(bmeta_path):
            continue
        try:
            bmeta = json.load(open(bmeta_path))
        except json.JSONDecodeError:
            import sys
            print("    # SKIPPED %s_%s: corrupt bounty_metadata.json" % (system, bounty_num), file=sys.stderr)
            continue

        name = system + "_" + bounty_num
        cwe = bmeta.get("CWE", bmeta.get("cwe_id", ""))
        cve = bmeta.get("CVE", "")
        if cwe and cve:
            cwe_full = cwe + " (" + cve + ")"
        elif cwe:
            cwe_full = cwe
        elif cve:
            cwe_full = cve
        else:
            cwe_full = ""

        patch = bmeta.get("patch", {})
        vuln_files = "; ".join(v.replace("codebase/", "") for v in patch.values()) if patch else ""

        severity = bmeta.get("severity", "")
        desc_parts = []
        if cwe:
            desc_parts.append(cwe)
        if severity:
            desc_parts.append("severity=" + str(severity))
        if vuln_files:
            first_file = vuln_files.split(";")[0].strip()
            desc_parts.append("patch in " + first_file)
        vuln_desc = "; ".join(desc_parts) if desc_parts else ""

        docker_str = "True" if has_docker else "False"
        # Escape any quotes
        cwe_full = cwe_full.replace('"', "'")
        vuln_files = vuln_files.replace('"', "'")
        vuln_desc = vuln_desc.replace('"', "'")

        print('    {"name": "%s", "task_dir": "bountytasks/%s", "bounty": "%s",' % (name, system, bounty_num))
        print('     "docker": %s, "timeout": 1800,' % docker_str)
        print('     "cwe": "%s",' % cwe_full)
        print('     "vuln_files": "%s",' % vuln_files)
        print('     "vuln_desc": "%s",' % vuln_desc)
        print('     "difficulty": ""},')
