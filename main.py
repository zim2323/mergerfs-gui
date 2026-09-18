import sys
import json
import subprocess
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QListWidget, QListWidgetItem, 
                             QPushButton, QGroupBox, QMessageBox)
from PyQt6.QtCore import Qt

class MergerfsDrivePoolApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Linux DrivePool Manager (mergerfs)")
        self.setGeometry(150, 150, 850, 500)
        
        # Main Layout (Horizontal split)
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)
        
        # LEFT PANEL: Disk Inventory
        left_panel = QGroupBox("Available Physical Storage Devices")
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        
        self.disk_list = QListWidget()
        left_layout.addWidget(self.disk_list)
        
        self.refresh_btn = QPushButton("🔄 Scan System for Drives")
        self.refresh_btn.clicked.connect(self.populate_disks)
        left_layout.addWidget(self.refresh_btn)
        
        # RIGHT PANEL: Pool Control & Automation
        right_panel = QGroupBox("Pool Actions & Automation")
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        
        self.pool_status_lbl = QLabel("Pool Status: <b>Not Tracked</b>")
        right_layout.addWidget(self.pool_status_lbl)
        
        self.create_pool_btn = QPushButton("➕ Create Mergerfs Pool from Selected")
        self.create_pool_btn.clicked.connect(self.create_pool_action)
        right_layout.addWidget(self.create_pool_btn)
        
        self.sync_btn = QPushButton("⚡ Trigger Duplication (mergerfs.dup)")
        right_layout.addWidget(self.sync_btn)
        
        # Assemble UI
        main_layout.addWidget(left_panel, stretch=2)
        main_layout.addWidget(right_panel, stretch=1)
        
        # Initial Scan
        self.populate_disks()

    def scan_system_disks(self):
        """Queries the system hardware for unmounted storage blocks using JSON output."""
        try:
            cmd = ["lsblk", "-J", "-o", "NAME,PATH,UUID,FSTYPE,SIZE,MOUNTPOINT"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            raw_devices = data.get("blockdevices", [])
            valid_candidates = []
            
            for dev in raw_devices:
                # Resolve partitions or fall back to base device if no children
                partitions = dev.get("children", [dev])
                for part in partitions:
                    # Filter out system root layouts, boot loaders, or empty partitions
                    # For safety in testing, we look for standard formatted data drives
                    if part.get("fstype") in ["xfs", "ext4", "btrfs"] and not part.get("mountpoint"):
                        valid_candidates.append({
                            "name": part.get("name"),
                            "path": part.get("path"),
                            "uuid": part.get("uuid"),
                            "fstype": part.get("fstype"),
                            "size": part.get("size")
                        })
            return valid_candidates
        except Exception as e:
            QMessageBox.critical(self, "Hardware Scan Error", f"Could not scan storage hardware:\n{str(e)}")
            return []

    def populate_disks(self):
        """Clears the visual list and redraws discovered disk infrastructure."""
        self.disk_list.clear()
        disks = self.scan_system_disks()
        
        if not disks:
            item = QListWidgetItem("No available/unmounted pool disks detected.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.disk_list.addItem(item)
            return

        for disk in disks:
            # Format look and feel string for easy user mapping
            display_text = f"💾 {disk['name']} [{disk['size']}] - Type: {disk['fstype'].upper()}\n   UUID: {disk['uuid']}"
            item = QListWidgetItem(display_text)
            
            # Save raw storage metadata directly inside the PyQt GUI list item container
            item.setData(Qt.ItemDataRole.UserRole, disk)
            
            # Make item explicitly multi-selectable via checkboxes
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            
            self.disk_list.addItem(item)

    def create_pool_action(self):
        """Iterates over checked items to verify targeting selections."""
        selected_uuids = []
        for i in range(self.disk_list.count()):
            item = self.disk_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                disk_data = item.data(Qt.ItemDataRole.UserRole)
                if disk_data:
                    selected_uuids.append(disk_data['uuid'])
                    
        if not selected_uuids:
            QMessageBox.warning(self, "No Selection", "Please check at least one hard drive to add to the new pool structure.")
            return
            
        QMessageBox.information(self, "Pool Builder Intelligence", 
                                f"Captured {len(selected_uuids)} drive UUIDs for processing!\n\nTargeting:\n" + "\n".join(selected_uuids))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MergerfsDrivePoolApp()
    window.show()
    sys.exit(app.exec())
