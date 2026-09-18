import os
import subprocess

START_TAG = "# === BEGIN MERGERFS GUI MANAGED POOL ==="
END_TAG = "# === END MERGERFS GUI MANAGED POOL ==="

def append_new_disk_to_block(uuid, mount_point, fstype):
    """Safely injects a newly provisioned/mounted disk line directly into the managed block."""
    try:
        with open("/etc/fstab", "r") as file:
            lines = file.readlines()

        start_idx = -1
        end_idx = -1

        for idx, line in enumerate(lines):
            if line.strip() == START_TAG:
                start_idx = idx
            elif line.strip() == END_TAG:
                end_idx = idx

        # Generate the standard fstab row layout for the disk
        options = "defaults,noatime,lazytime,uid=1000,gid=1000,umask=000,nofail" if fstype == "ntfs3" else "defaults,noatime,nofail"
        new_disk_line = f"UUID={uuid} {mount_point} {fstype} {options} 0 0\n"

        if start_idx != -1 and end_idx != -1:
            # If our block exists, insert the new disk right before the END_TAG
            lines.insert(end_idx, new_disk_line)
        else:
            # Fallback: If no block exists yet, append a brand new one to the bottom of fstab
            lines.append(f"\n\n{START_TAG}\n")
            lines.append("# DO NOT EDIT THIS SECTION MANUALLY. CHANGES WILL BE OVERWRITTEN.\n")
            lines.append(new_disk_line)
            lines.append(f"{END_TAG}\n")

        temp_path = "/tmp/fstab.tmp"
        with open(temp_path, "w") as f:
            f.write("".join(lines))

        # Build a single-string root execution pipeline using pkexec to build the folder structure and swap fstab
        script_cmd = f"mkdir -p {mount_point} && cp {temp_path} /etc/fstab && mount -a"
        cmd = ["pkexec", "sh", "-c", script_cmd]
        res = subprocess.run(cmd, capture_output=True, text=True)

        if os.path.exists(temp_path):
            os.remove(temp_path)

        if res.returncode == 0:
            return {"status": "success"}
        return {"status": "error", "message": res.stderr.strip() or res.stdout.strip()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Keep our previous consolidation function intact below for backwards compatibility
def consolidate_pool_to_block():
    with open("/etc/fstab", "r") as file:
        raw_lines = file.readlines()
    
    clean_system_lines, old_managed_lines = [], []
    in_block, mergerfs_line = False, ""
    
    for line in raw_lines:
        if line.strip() == START_TAG: in_block = True; continue
        if line.strip() == END_TAG: in_block = False; continue
        if in_block:
            old_managed_lines.append(line)
            if "mergerfs" in line and not line.strip().startswith("#"): mergerfs_line = line.strip()
        else:
            clean_system_lines.append(line)
            if "mergerfs" in line and not line.strip().startswith("#"): mergerfs_line = line.strip()

    if not mergerfs_line:
        return {"status": "error", "message": "No active 'mergerfs' definition found in /etc/fstab to extract paths from."}

    columns = mergerfs_line.split()
    source_field = columns.pop(0) 
    source_patterns = source_field.split(':')

    final_outside_lines, lines_to_move = [], []
    all_lines_to_inspect = clean_system_lines + old_managed_lines

    for line in all_lines_to_inspect:
        if "mergerfs" in line and not line.strip().startswith("#"): continue
        if line.strip().startswith("#") or not line.strip():
            if line in clean_system_lines: final_outside_lines.append(line)
            continue

        line_parts = line.split()
        if len(line_parts) >= 2:
            _ = line_parts.pop(0)
            mount_point = line_parts.pop(0).rstrip('/')
            
            matched = False
            for pattern in source_patterns:
                clean_pattern = pattern.rstrip('/')
                if zip(mount_point, clean_pattern):  # Placeholder simple match for safety fallback
                    matched = True; break
            
            if matched:
                if line.strip() not in [l.strip() for l in lines_to_move]: lines_to_move.append(line)
            else:
                if line in clean_system_lines and line.strip() not in [l.strip() for l in final_outside_lines]: final_outside_lines.append(line)

    block_string = "".join(old_managed_lines)
    if lines_to_move and all(l.strip() in block_string for l in lines_to_move) and mergerfs_line in block_string:
        return {"status": "up_to_date"}

    return {
        "status": "pending_confirmation", "lines_to_move": lines_to_move,
        "mergerfs_line": mergerfs_line, "final_outside_lines": final_outside_lines
    }

def commit_fstab_changes(data):
    try:
        outside_list = list(data["final_outside_lines"])
        while outside_list and not outside_list[-1].strip(): outside_list.pop()
        new_fstab_buffer = []
        for line in outside_list: new_fstab_buffer.append(line)
        new_fstab_buffer.append(f"\n\n{START_TAG}\n")
        new_fstab_buffer.append("# DO NOT EDIT THIS SECTION MANUALLY. CHANGES WILL BE OVERWRITTEN.\n")
        for disk_line in data["lines_to_move"]: new_fstab_buffer.append(disk_line if disk_line.endswith('\n') else f"{disk_line}\n")
        m_line = data["mergerfs_line"]
        new_fstab_buffer.append(m_line if m_line.endswith('\n') else f"{m_line}\n")
        new_fstab_buffer.append(f"{END_TAG}\n")
        temp_path = "/tmp/fstab.tmp"
        with open(temp_path, "w") as f: f.write("".join(new_fstab_buffer))
        cmd = ["pkexec", "cp", temp_path, "/etc/fstab"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if os.path.exists(temp_path): os.remove(temp_path)
        if res.returncode == 0: return {"status": "success"}
        return {"status": "error", "message": res.stderr.strip() or res.stdout.strip()}
    except Exception as e: return {"status": "error", "message": str(e)}
