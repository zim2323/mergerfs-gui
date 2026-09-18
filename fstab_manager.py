import os
import fnmatch
import subprocess

START_TAG = "# === BEGIN MERGERFS GUI MANAGED POOL ==="
END_TAG = "# === END MERGERFS GUI MANAGED POOL ==="

def consolidate_pool_to_block():
    with open("/etc/fstab", "r") as file:
        raw_lines = file.readlines()
    
    clean_system_lines = []
    old_managed_lines = []
    in_block = False
    mergerfs_line = ""
    
    # 1. Isolate the block contents to find the active mergerfs definition
    for line in raw_lines:
        if line.strip() == START_TAG:
            in_block = True
            continue
        if line.strip() == END_TAG:
            in_block = False
            continue
            
        if in_block:
            old_managed_lines.append(line)
            if "mergerfs" in line and not line.strip().startswith("#"):
                mergerfs_line = line.strip()
        else:
            clean_system_lines.append(line)
            if "mergerfs" in line and not line.strip().startswith("#"):
                mergerfs_line = line.strip()

    if not mergerfs_line:
        return {"status": "error", "message": "No active 'mergerfs' definition found in /etc/fstab to extract paths from."}

    # 2. Extract column 1 (Source field) dynamically without bracket syntax
    columns = mergerfs_line.split()
    source_field = columns.pop(0) 
    source_patterns = source_field.split(':')

    final_outside_lines = []
    lines_to_move = []
    all_lines_to_inspect = clean_system_lines + old_managed_lines

    # 3. Match physical disks purely against what the mergerfs string actually uses
    for line in all_lines_to_inspect:
        if "mergerfs" in line and not line.strip().startswith("#"):
            continue
        if line.strip().startswith("#") or not line.strip():
            if line in clean_system_lines:
                final_outside_lines.append(line)
            continue

        line_parts = line.split()
        if len(line_parts) >= 2:
            _ = line_parts.pop(0) # Remove Column 1 (UUID/Dev)
            mount_point = line_parts.pop(0).rstrip('/') # Grab Column 2 (Local Mount Path)
            
            matched = False
            for pattern in source_patterns:
                clean_pattern = pattern.rstrip('/')
                
                # Dynamic matching rules (Handles exact paths, wildcards like *, or prefix matches)
                if fnmatch.fnmatch(mount_point, clean_pattern):
                    matched = True
                    break
                elif clean_pattern.endswith('*') and mount_point.startswith(clean_pattern[:-1]):
                    matched = True
                    break
                elif clean_pattern in mount_point:
                    matched = True
                    break
            
            if matched:
                if line.strip() not in [l.strip() for l in lines_to_move]:
                    lines_to_move.append(line)
            else:
                if line in clean_system_lines and line.strip() not in [l.strip() for l in final_outside_lines]:
                    final_outside_lines.append(line)

    # 4. Check if we actually need to write changes
    block_string = "".join(old_managed_lines)
    drives_nested = all(l.strip() in block_string for l in lines_to_move) if lines_to_move else False
    pool_nested = mergerfs_line in block_string

    if lines_to_move and drives_nested and pool_nested:
        return {"status": "up_to_date"}

    return {
        "status": "pending_confirmation",
        "lines_to_move": lines_to_move,
        "mergerfs_line": mergerfs_line,
        "final_outside_lines": final_outside_lines
    }

def commit_fstab_changes(data):
    try:
        outside_list = list(data["final_outside_lines"])
        while outside_list and not outside_list[-1].strip():
            outside_list.pop()

        new_fstab_buffer = []
        for line in outside_list:
            new_fstab_buffer.append(line)
            
        new_fstab_buffer.append(f"\n\n{START_TAG}\n")
        new_fstab_buffer.append("# DO NOT EDIT THIS SECTION MANUALLY. CHANGES WILL BE OVERWRITTEN.\n")
        
        for disk_line in data["lines_to_move"]:
            new_fstab_buffer.append(disk_line if disk_line.endswith('\n') else f"{disk_line}\n")
            
        m_line = data["mergerfs_line"]
        new_fstab_buffer.append(m_line if m_line.endswith('\n') else f"{m_line}\n")
        new_fstab_buffer.append(f"{END_TAG}\n")

        temp_path = "/tmp/fstab.tmp"
        with open(temp_path, "w") as f:
            f.write("".join(new_fstab_buffer))

        cmd = ["pkexec", "cp", temp_path, "/etc/fstab"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        if res.returncode == 0:
            return {"status": "success"}
        return {"status": "error", "message": res.stderr.strip() or res.stdout.strip()}
    except Exception as e:
        return {"status": "error", "message": str(e)}
