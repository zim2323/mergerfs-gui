import sys
import json
import subprocess
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QListWidget, QListWidgetItem, 
                             QPushButton, QGroupBox, QMessageBox)
from PyQt6.QtCore import Qt
import fstab_manager

class MergerfsDrivePoolApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Linux DrivePool Manager (mergerfs)")
        self.setGeometry(150, 150, 850, 500)
        
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)
        
        # LEFT PANEL
        left_panel = QGroupBox("Available Physical Storage Devices")
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        self.disk_list = QListWidget()
        left_layout.addWidget(self.disk_list)
        self.refresh_btn = QPushButton("🔄 Scan System for Drives")
        self.refresh_btn.clicked.connect(self.populate_disks)
        left_layout.addWidget(self.refresh_btn)
        
        # RIGHT PANEL
        right_panel = QGroupBox("Pool Actions & Automation")
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        self.pool_status_lbl = QLabel("Pool Status: <b>Tracking System Layout</b>")
        right_layout.addWidget(self.pool_status_lbl)
        
        self.create_pool_btn = QPushButton("🔒 Claim & Move Pool + Disks Into Managed Block")
        self.create_pool_btn.clicked.connect(self.run_consolidation)
        right_layout.addWidget(self.create_pool_btn)
        
        self.sync_btn = QPushButton("⚡ Trigger Duplication (mergerfs.dup)")
        right_layout.addWidget(self.sync_btn)
        
        main_layout.addWidget(left_panel, stretch=2)
        main_layout.addWidget(right_panel, stretch=1)
        self.populate_disks()

    def scan_system_disks(self):
        try:
            cmd = ["lsblk", "-J", "-o", "NAME,PATH,UUID,FSTYPE,SIZE,MOUNTPOINT"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            devices = json.loads(res.stdout).get("blockdevices", [])
            valid = []
            for dev in devices:
                for part in dev.get("children", [dev]):
                    if part.get("fstype") != "swap":
                        valid.append({
                            "name": part.get("name"), "path": part.get("path"),
                            "uuid": part.get("uuid") or "NO_UUID_FOUND",
                            "fstype": part.get("fstype") or "unformatted/raw",
                            "size": part.get("size"), "mountpoint": part.get("mountpoint") or "Not Mounted"
                        })
            return valid
        except Exception as e:
            QMessageBox.critical(self, "Hardware Scan Error", str(e))
            return []

    def populate_disks(self):
        self.disk_list.clear()
        for d in self.scan_system_disks():
            txt = f"💾 {d['name']} [{d['size']}] - Type: {d['fstype'].upper()}\n   Mount: {d['mountpoint']}\n   UUID: {d['uuid']}"
            item = QListWidgetItem(txt)
            item.setData(Qt.ItemDataRole.UserRole, d)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.disk_list.addItem(item)

    def run_consolidation(self):
        res = fstab_manager.consolidate_pool_to_block()
        if res["status"] == "error":
            QMessageBox.warning(self, "No Pool Found", res["message"])
        elif res["status"] == "up_to_date":
            QMessageBox.information(self, "Up to Date", "Your mergerfs pool configuration is already perfectly aligned inside the managed block!")
        elif res["status"] == "pending_confirmation":
            msg = "Found pool lines to move inside the managed block:\n\n"
            for l in res["lines_to_move"]: msg += f"➡️ Disk: {l.strip()}\n"
            msg += f"➡️ Pool: {res['mergerfs_line']}\n"
            
            reply = QMessageBox.question(self, "Confirm Consolidation", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                commit_res = fstab_manager.commit_fstab_changes(res)
                if commit_res["status"] == "success":
                    QMessageBox.information(self, "Success!", "Consolidated your array configuration into the managed block!")
                else:
                    # THIS BOX WILL NOW TELL US THE EXACT PROBLEM
                    QMessageBox.critical(self, "System Write Failure", f"Linux blocked the file update.\n\nReason:\n{commit_res['message']}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MergerfsDrivePoolApp()
    window.show()
    sys.exit(app.exec())
