import sys
import json
import subprocess
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QListWidget, QListWidgetItem, 
                             QPushButton, QGroupBox, QMessageBox, QDialog, QLineEdit, QComboBox)
from PyQt6.QtCore import Qt
import fstab_manager

class NewMemberDiskWizard(QDialog):
    def __init__(self, disk_data, parent=None):
        super().__init__(parent)
        self.disk_data = disk_data
        self.setWindowTitle(f"Provision Storage Device: {disk_data['name']}")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        layout.addWidget(QLabel(f"<b>Device:</b> {disk_data['path']} ({disk_data['size']})"))
        layout.addWidget(QLabel(f"<b>UUID:</b> {disk_data['uuid']}"))
        layout.addWidget(QLabel("<br>Assign a custom naming schema to mount this drive natively into Linux:"))
        
        # Folder Naming Form Row
        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Mount Target Path:  <b>/mnt/</b>"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., data1, games, storage_01")
        form_layout.addWidget(self.name_input)
        layout.addLayout(form_layout)
        
        # Filesystem type Selector Row
        fs_layout = QHBoxLayout()
        fs_layout.addWidget(QLabel("File System Driver (FSTYPE):"))
        self.fs_combo = QComboBox()
        self.fs_combo.addItems(["ntfs3", "ext4", "xfs", "btrfs"])
        detected_fs = disk_data['fstype'].lower()
        if "unformatted" not in detected_fs:
            index = self.fs_combo.findText(detected_fs)
            if index >= 0: self.fs_combo.setCurrentIndex(index)
        fs_layout.addWidget(self.fs_combo)
        layout.addLayout(fs_layout)
        
        layout.addWidget(QLabel("<small style='color: gray;'>Note: Clicking 'Mount & Add' will create the directories under /mnt and update your /etc/fstab securely via Polkit.</small>"))
        
        # Submissions Options Array
        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.submit_btn = QPushButton("🔒 Mount & Add to Block")
        self.submit_btn.clicked.connect(self.process_provisioning)
        
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.submit_btn)
        layout.addLayout(btn_layout)
        
        self.result_data = None

    def process_provisioning(self):
        folder_name = self.name_input.text().strip()
        if not folder_name or any(c in folder_name for c in ["/", " ", "\\", "*", "?", ";"]):
            QMessageBox.warning(self, "Invalid Name", "Please specify an alphanumeric directory name without spaces or slashes.")
            return
            
        if self.disk_data['uuid'] == "NO_UUID_FOUND":
            QMessageBox.critical(self, "Missing Unique ID", "This drive does not possess a valid UUID and cannot be securely mounted via fstab.")
            return

        target_mount = f"/mnt/{folder_name}"
        selected_fs = self.fs_combo.currentText()
        
        res = fstab_manager.append_new_disk_to_block(self.disk_data['uuid'], target_mount, selected_fs)
        
        if res["status"] == "success":
            QMessageBox.information(self, "Success!", f"Successfully created directory, appended storage configurations, and mounted {target_mount} cleanly!")
            self.accept()
        else:
            QMessageBox.critical(self, "Elevated Write Failed", f"Could not provision drive hardware.\n\nError details:\n{res['message']}")

class MergerfsDrivePoolApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Linux DrivePool Manager (mergerfs)")
        self.setGeometry(150, 150, 850, 500)
        
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)
        
        # LEFT PANEL: Disk Inventory Setup
        left_panel = QGroupBox("Available Physical Storage Devices")
        left_layout = QVBoxLayout()
        
        self.disk_list = QListWidget()
        self.disk_list.itemChanged.connect(self.handle_disk_selection_intercept)
        left_layout.addWidget(self.disk_list)
        
        self.refresh_btn = QPushButton("🔄 Scan System for Drives")
        self.refresh_btn.clicked.connect(self.populate_disks)
        left_layout.addWidget(self.refresh_btn)
        
        # FIX: Explicitly map the layout directly onto the QGroupBox container widget
        left_panel.setLayout(left_layout)
        
        # RIGHT PANEL: Pool Control & Operations Setup
        right_panel = QGroupBox("Pool Actions & Automation")
        right_layout = QVBoxLayout()
        
        self.pool_status_lbl = QLabel("Pool Status: <b>Tracking System Layout</b>")
        right_layout.addWidget(self.pool_status_lbl)
        
        self.create_pool_btn = QPushButton("🔒 Claim & Move Pool + Disks Into Managed Block")
        self.create_pool_btn.clicked.connect(self.run_consolidation)
        right_layout.addWidget(self.create_pool_btn)
        
        self.sync_btn = QPushButton("⚡ Trigger Duplication (mergerfs.dup)")
        right_layout.addWidget(self.sync_btn)
        
        # FIX: Explicitly map the layout directly onto the QGroupBox container widget
        right_panel.setLayout(right_layout)
        
        # Assemble UI view frame structures together
        main_layout.addWidget(left_panel, stretch=2)
        main_layout.addWidget(right_panel, stretch=1)
        
        self._initializing_list = False
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
        self._initializing_list = True
        self.disk_list.clear()
        for d in self.scan_system_disks():
            txt = f"💾 {d['name']} [{d['size']}] - Type: {d['fstype'].upper()}\n   Mount: {d['mountpoint']}\n   UUID: {d['uuid']}"
            item = QListWidgetItem(txt)
            item.setData(Qt.ItemDataRole.UserRole, d)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.disk_list.addItem(item)
        self._initializing_list = False

    def handle_disk_selection_intercept(self, item):
        if self._initializing_list: return
        
        if item.checkState() == Qt.CheckState.Checked:
            disk_data = item.data(Qt.ItemDataRole.UserRole)
            if disk_data and disk_data["mountpoint"] == "Not Mounted":
                self._initializing_list = True
                item.setCheckState(Qt.CheckState.Unchecked)
                self._initializing_list = False
                
                wizard = NewMemberDiskWizard(disk_data, self)
                if wizard.exec() == QDialog.DialogCode.Accepted:
                    self.populate_disks()

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
                    QMessageBox.critical(self, "System Write Failure", f"Linux blocked the file update.\n\nReason:\n{commit_res['message']}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MergerfsDrivePoolApp()
    window.show()
    sys.exit(app.exec())
