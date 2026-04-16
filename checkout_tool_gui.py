"""
checkout_tool_gui.py — Phoenix Valve Checkout Tool
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDate, Qt, QSettings, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateEdit, QDialog,
    QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSplitter,
    QTabWidget, QTableWidget, QTableWidgetItem, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from checkout_tool_backend import CheckoutStore, Job, ValveCheckout
from checkout_export import export_records
from version import __version__
import updater


# ── Wiring structure constants ────────────────────────────────────────────────
# Each entry: (section_title, row_num, point, descriptor, is_factory)

PHOENIX_WIRING: list[tuple] = [
    ("TB1 \u2014 INPUTS",                                          1, "UI-1 +",              "Sash Open Signal",               False),
    ("TB1 \u2014 INPUTS",                                          2, "UI-1 \u2212",         "Sash Open Signal",               False),
    ("TB1 \u2014 INPUTS",                                          3, "UI-2 +",              "",                               False),
    ("TB1 \u2014 INPUTS",                                          4, "UI-2 \u2212",         "",                               False),
    ("TB1 \u2014 INPUTS",                                          5, "UI-3 +",              "",                               False),
    ("TB1 \u2014 INPUTS",                                          6, "UI-3 \u2212",         "",                               False),
    ("TB1 \u2014 INPUTS",                                          7, "DI-1 +",              "",                               False),
    ("TB1 \u2014 INPUTS",                                          8, "DI-1 \u2212",         "",                               False),
    ("TB2 \u2014 OUTPUTS",                                         1, "DO-0 N.O.",            "Valve Alarm (if needed)",        False),
    ("TB2 \u2014 OUTPUTS",                                         2, "Common",               "Valve Alarm (if needed)",        False),
    ("TB2 \u2014 OUTPUTS",                                         3, "DO-0 N.C.",            "",                               False),
    ("TB2 \u2014 OUTPUTS",                                         4, "AO-1 +",               "Flow Feedback 0\u201310V (opt)", False),
    ("TB2 \u2014 OUTPUTS",                                         5, "GROUND",               "Flow Feedback 0\u201310V (opt)", False),
    ("TB2 \u2014 OUTPUTS",                                         6, "AO-2",                 "",                               False),
    ("TB2 \u2014 OUTPUTS",                                         7, "GROUND",               "",                               False),
    ("TB3 \u2014 INTERNAL  (Factory Wired \u2014 Do Not Modify)",  1, "RED / VPOT",           "Valve Position Feedback",        True),
    ("TB3 \u2014 INTERNAL  (Factory Wired \u2014 Do Not Modify)",  2, "GREEN / VPOT",         "",                               True),
    ("TB3 \u2014 INTERNAL  (Factory Wired \u2014 Do Not Modify)",  3, "BLACK / VPOT",         "",                               True),
    ("TB3 \u2014 INTERNAL  (Factory Wired \u2014 Do Not Modify)",  4, "PRESSURE SW (R)",      "Pressure Switch Dry Contact",    True),
    ("TB3 \u2014 INTERNAL  (Factory Wired \u2014 Do Not Modify)",  5, "PRESSURE SW (B)",      "",                               True),
    ("TB4 \u2014 POWER",                                           1, "L1 HOT",               "24 VAC",                         False),
    ("TB4 \u2014 POWER",                                           2, "L2 COMMON",            "24 VAC",                         False),
    ("TB4 \u2014 POWER",                                           3, "GROUND",               "",                               False),
    ("TB6 \u2014 COMM",                                            1, "A  (WHT)",             "LON Network-1",                  False),
    ("TB6 \u2014 COMM",                                            2, "B  (BLU)",             "LON Network-2",                  False),
    ("TB7 \u2014 ACTUATOR  (Factory Wired \u2014 Do Not Modify)",  1, "ACTUATOR",             "BLACK",                          True),
    ("TB7 \u2014 ACTUATOR  (Factory Wired \u2014 Do Not Modify)",  2, "ACTUATOR",             "RED",                            True),
]

BB_WIRING: list[tuple] = [
    ("TB1 \u2014 POWER IN",                        1, "L1 +",      "24 VAC",                         False),
    ("TB1 \u2014 POWER IN",                        2, "GROUND",    "",                               False),
    ("TB1 \u2014 POWER IN",                        3, "L2 \u2212", "24 VAC",                         False),
    ("TB2 \u2014 OUTPUTS",                         1, "V OUT",     "\u2192 Phoenix UI-1 +",           False),
    ("TB2 \u2014 OUTPUTS",                         2, "Ground",    "\u2192 Phoenix UI-1 \u2212",      False),
    ("TB3 \u2014 INPUTS",                          1, "IN-1 +",    "Vertical Sash Sensor",            False),
    ("TB3 \u2014 INPUTS",                          2, "IN-1 \u2212","Vertical Sash Sensor",           False),
    ("FHM Sentry \u2014 Fume Hood Monitor",        1, "A  (WHT)",  "LON Network-1",                   False),
    ("FHM Sentry \u2014 Fume Hood Monitor",        2, "B  (BLU)",  "LON Network-2",                   False),
    ("FHM Sentry \u2014 Fume Hood Monitor",        3, "L1 +",      "24 VAC",                          False),
    ("FHM Sentry \u2014 Fume Hood Monitor",        4, "L2 \u2212", "24 VAC",                          False),
]

CONFIG_ROWS: list[tuple[str, str]] = [
    ("valve_min",     "Valve Min."),
    ("valve_max",     "Valve Max."),
    ("sched_min",     "Scheduled Min."),
    ("sched_max",     "Scheduled Max."),
    ("hood_sash_min", "Hood Sash Min."),
    ("hood_sash_max", "Hood Sash Max."),
]

VERIFY_ROWS: list[tuple[str, str]] = [
    ("face_velocity",      'Face Velocity @ 18"'),
    ("sash_height_alarm",  "Sash Height Alarm"),
    ("sash_sensor_output", "Sash Sensor Output"),
    ("low_flow_alarm",     "Low Flow Alarm"),
    ("jam_alarm",          "JAM Alarm"),
    ("emergency_exhaust",  "Emergency Exhaust Override"),
    ("mute_function",      "Mute Function"),
]

# Pass/Fail tree item colors (work on both light and dark backgrounds)
_PASS_COLOR = QColor(55, 195, 100)
_FAIL_COLOR = QColor(220, 70,  70)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resource_path(filename: str) -> str:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", ""))
    else:
        base = Path(__file__).parent
    return str(base / filename)


def _app_data_path(filename: str) -> str:
    base = Path(os.environ.get("APPDATA", Path.home())) / "ATS Inc" / "Phoenix Valve Checkout Tool"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / filename)


def _centered_checkbox(checked: bool = False, enabled: bool = True) -> tuple[QWidget, QCheckBox]:
    """Return (container_widget, checkbox) suitable for QTableWidget.setCellWidget."""
    container = QWidget()
    lay = QHBoxLayout(container)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
    cb = QCheckBox()
    cb.setChecked(checked)
    cb.setEnabled(enabled)
    lay.addWidget(cb)
    return container, cb


def _job_label(job: Job) -> str:
    if job.job_number and job.job_name:
        return f"{job.job_number}  \u2014  {job.job_name}"
    return job.job_number or job.job_name or "(Unnamed Job)"


# ── Update worker ─────────────────────────────────────────────────────────────

class _UpdateChecker(QThread):
    found = Signal(object)

    def run(self) -> None:
        info = updater.check_for_update()
        if info:
            self.found.emit(info)


# ── Dialogs ───────────────────────────────────────────────────────────────────

class NewJobDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Job")
        self.setModal(True)
        self.resize(400, 160)

        self._job_number = QLineEdit()
        self._job_name   = QLineEdit()

        form = QFormLayout()
        form.addRow("Job Number *", self._job_number)
        form.addRow("Job Name *",   self._job_name)

        btns = QDialogButtonBox()
        btns.addButton(QDialogButtonBox.StandardButton.Ok)
        btns.addButton(QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(btns)

    def accept(self) -> None:
        if not self._job_number.text().strip():
            QMessageBox.warning(self, "Required", "Job Number is required.")
            return
        if not self._job_name.text().strip():
            QMessageBox.warning(self, "Required", "Job Name is required.")
            return
        super().accept()

    def get_job(self) -> Job:
        return Job(
            job_number=self._job_number.text().strip(),
            job_name=self._job_name.text().strip(),
        )


class NewCheckoutDialog(QDialog):
    def __init__(self, job: Job, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._job = job
        self.setWindowTitle(f"New Checkout  \u2014  {_job_label(job)}")
        self.setModal(True)
        self.resize(440, 220)

        self._valve_tag   = QLineEdit()
        self._technician  = QLineEdit()
        self._description = QLineEdit()
        self._date = QDateEdit(QDate.currentDate())
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("yyyy-MM-dd")

        form = QFormLayout()
        form.addRow("Valve Tag # *", self._valve_tag)
        form.addRow("Technician",    self._technician)
        form.addRow("Description",   self._description)
        form.addRow("Date",          self._date)

        btns = QDialogButtonBox()
        btns.addButton(QDialogButtonBox.StandardButton.Ok)
        btns.addButton(QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(btns)

    def accept(self) -> None:
        if not self._valve_tag.text().strip():
            QMessageBox.warning(self, "Required", "Valve Tag # is required.")
            return
        super().accept()

    def get_record(self) -> ValveCheckout:
        return ValveCheckout(
            job_id=self._job.id,
            valve_tag=self._valve_tag.text().strip(),
            project=self._job.job_name,
            ats_job_number=self._job.job_number,
            technician=self._technician.text().strip(),
            description=self._description.text().strip(),
            date=self._date.date().toString("yyyy-MM-dd"),
        )


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    APP_NAME = "Phoenix Valve Checkout Tool"

    # UserRole tuple stored on tree items: ("job", job_id) or ("checkout", record_id)
    _ROLE = Qt.ItemDataRole.UserRole

    def __init__(self) -> None:
        super().__init__()
        self._store = CheckoutStore()
        self._current_id: Optional[str] = None   # selected checkout id
        self._loading = False

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(350)
        self._save_timer.timeout.connect(self._save_current)

        self._update_info: Optional[updater.UpdateInfo] = None

        self.setWindowTitle(f"{self.APP_NAME} \u2014 v{__version__}")
        self.resize(1380, 840)

        icon_path = _resource_path("PTT_Normal.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._build_menu()
        self._build_ui()
        self._restore_settings()
        self._refresh_tree()
        self._check_for_updates()

    # ── Menu bar ──────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("File")
        new_job_act = QAction("New Job", self)
        new_job_act.setShortcut("Ctrl+J")
        new_job_act.triggered.connect(self._on_new_job)
        file_menu.addAction(new_job_act)
        new_co_act = QAction("New Checkout", self)
        new_co_act.setShortcut("Ctrl+N")
        new_co_act.triggered.connect(self._on_new_checkout)
        file_menu.addAction(new_co_act)
        file_menu.addSeparator()
        export_act = QAction("Export Selected Checkout\u2026", self)
        export_act.setShortcut("Ctrl+E")
        export_act.triggered.connect(self._on_export_current)
        file_menu.addAction(export_act)
        export_job_act = QAction("Export All Checkouts in Job\u2026", self)
        export_job_act.triggered.connect(self._on_export_job)
        file_menu.addAction(export_job_act)
        file_menu.addSeparator()
        exit_act = QAction("Exit", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        view_menu = mb.addMenu("View")
        self._dark_mode_action = QAction("Dark Mode", self)
        self._dark_mode_action.setCheckable(True)
        s = QSettings("ATS Inc", self.APP_NAME)
        self._dark_mode_action.setChecked(s.value("darkMode", "true") != "false")
        self._dark_mode_action.triggered.connect(self._toggle_dark_mode)
        view_menu.addAction(self._dark_mode_action)

        help_menu = mb.addMenu("Help")
        about_act = QAction(f"About {self.APP_NAME}", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    # ── Top-level layout ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget()
        root_lay = QHBoxLayout(root)
        root_lay.setContentsMargins(8, 8, 8, 8)
        root_lay.setSpacing(8)
        self.setCentralWidget(root)
        root_lay.addWidget(self._build_sidebar())
        root_lay.addWidget(self._build_main_area(), stretch=1)

    # ── Sidebar (job tree) ────────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(270)
        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        new_job_btn = QPushButton("+ New Job")
        new_job_btn.clicked.connect(self._on_new_job)
        self._new_checkout_btn = QPushButton("+ New Checkout")
        self._new_checkout_btn.clicked.connect(self._on_new_checkout)
        self._new_checkout_btn.setEnabled(False)
        btn_row.addWidget(new_job_btn)
        btn_row.addWidget(self._new_checkout_btn)
        lay.addLayout(btn_row)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(1)
        self._tree.setIndentation(18)
        self._tree.currentItemChanged.connect(self._on_tree_changed)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        lay.addWidget(self._tree)

        return sidebar

    # ── Main area ─────────────────────────────────────────────────────────────

    def _build_main_area(self) -> QWidget:
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(self._build_header_panel())
        lay.addWidget(self._build_tabs(), stretch=1)

        self._update_banner = self._build_update_banner()
        self._update_banner.setVisible(False)
        lay.addWidget(self._update_banner)
        return widget

    # ── Header panel ─────────────────────────────────────────────────────────

    def _build_header_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("Panel")
        panel.setFixedHeight(72)
        lay = QHBoxLayout(panel)
        lay.setContentsMargins(20, 10, 20, 10)
        lay.setSpacing(20)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._hdr_tag = QLabel("Select a job or checkout")
        self._hdr_tag.setObjectName("ProjectTitle")
        self._hdr_sub = QLabel("")
        self._hdr_sub.setObjectName("ProjectSubtitle")
        text_col.addWidget(self._hdr_tag)
        text_col.addWidget(self._hdr_sub)
        lay.addLayout(text_col)
        lay.addStretch()

        self._hdr_badge = QLabel("")
        self._hdr_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hdr_badge.setFixedSize(72, 32)
        lay.addWidget(self._hdr_badge)
        return panel

    # ── Tab widget ────────────────────────────────────────────────────────────

    def _build_tabs(self) -> QTabWidget:
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(),       "General")
        self._tabs.addTab(self._build_wiring_tab(),        "Wiring")
        self._tabs.addTab(self._build_config_verify_tab(), "Config & Verification")
        self._tabs.addTab(self._build_notes_tab(),         "Notes")
        self._tabs.setEnabled(False)
        return self._tabs

    # ── General tab ───────────────────────────────────────────────────────────

    def _build_general_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        inner = QWidget()
        outer = QVBoxLayout(inner)
        outer.setContentsMargins(0, 0, 8, 0)

        panel = QWidget()
        panel.setObjectName("Panel")
        form = QFormLayout(panel)
        form.setContentsMargins(24, 18, 24, 18)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        def le() -> QLineEdit:
            e = QLineEdit()
            e.textChanged.connect(self._on_any_change)
            return e

        self._f_valve_tag    = le()
        self._f_project      = le()
        self._f_job_number   = le()
        self._f_technician   = le()
        self._f_description  = le()
        self._f_model        = QLineEdit("CELERIS 2")
        self._f_model.textChanged.connect(self._on_any_change)

        self._f_date = QDateEdit(QDate.currentDate())
        self._f_date.setCalendarPopup(True)
        self._f_date.setDisplayFormat("yyyy-MM-dd")
        self._f_date.dateChanged.connect(self._on_any_change)

        self._f_pass_fail = QComboBox()
        self._f_pass_fail.addItems(["", "Pass", "Fail"])
        self._f_pass_fail.currentIndexChanged.connect(self._on_any_change)

        self._f_emer_min     = le()
        self._f_valve_min_sp = le()
        self._f_valve_max_sp = le()

        form.addRow("Valve Tag #",     self._f_valve_tag)
        form.addRow("Project",         self._f_project)
        form.addRow("ATS Job Number",  self._f_job_number)
        form.addRow("Technician",      self._f_technician)
        form.addRow("Description",     self._f_description)
        form.addRow("Model",           self._f_model)
        form.addRow("Date",            self._f_date)
        form.addRow("Pass / Fail",     self._f_pass_fail)
        form.addRow("Emer. Min (CFM)", self._f_emer_min)
        form.addRow("Valve Min SP",    self._f_valve_min_sp)
        form.addRow("Valve Max SP",    self._f_valve_max_sp)

        outer.addWidget(panel)
        outer.addStretch()
        scroll.setWidget(inner)
        return scroll

    # ── Wiring tab ────────────────────────────────────────────────────────────

    def _build_wiring_tab(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        phoenix_panel, self._phoenix_cbs = self._build_wiring_panel(
            "PHOENIX AIR VALVE  \u2014  Wiring", PHOENIX_WIRING, sash_sensor=True
        )
        bb_panel, self._bb_cbs = self._build_wiring_panel(
            "BLACK BOX  \u2014  Wiring", BB_WIRING, sash_sensor=False
        )
        splitter.addWidget(phoenix_panel)
        splitter.addWidget(bb_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        return splitter

    def _build_wiring_panel(
        self,
        title: str,
        wiring_def: list[tuple],
        sash_sensor: bool,
    ) -> tuple[QScrollArea, dict]:
        rows: list = []
        current_section = None
        for i, (section, num, point, descriptor, is_factory) in enumerate(wiring_def):
            if section != current_section:
                rows.append(("hdr", section))
                current_section = section
            rows.append(("row", i, num, point, descriptor, is_factory))

        table = QTableWidget(len(rows), 5)
        table.setHorizontalHeaderLabels(["#", "Point", "Descriptor", "Install", "Wired"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setAlternatingRowColors(False)
        hh = table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(3, 60)
        table.setColumnWidth(4, 60)

        checkboxes: dict = {}
        bold_font = QFont()
        bold_font.setBold(True)
        bold_font.setPointSize(9)

        for r_idx, row_data in enumerate(rows):
            if row_data[0] == "hdr":
                item = QTableWidgetItem(f"  {row_data[1]}")
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item.setFont(bold_font)
                table.setItem(r_idx, 0, item)
                table.setSpan(r_idx, 0, 1, 5)
                table.setRowHeight(r_idx, 26)
            else:
                _, w_idx, num, point, descriptor, is_factory = row_data
                table.setRowHeight(r_idx, 28)

                num_item = QTableWidgetItem(str(num))
                num_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(r_idx, 0, num_item)

                pt_item = QTableWidgetItem(point)
                pt_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                table.setItem(r_idx, 1, pt_item)

                desc_text = (
                    f"{descriptor}  \u2014  Factory" if (is_factory and descriptor)
                    else "Factory Wired" if is_factory
                    else descriptor
                )
                desc_item = QTableWidgetItem(desc_text)
                desc_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                table.setItem(r_idx, 2, desc_item)

                inst_w, inst_cb = _centered_checkbox(is_factory, enabled=not is_factory)
                table.setCellWidget(r_idx, 3, inst_w)
                if not is_factory:
                    checkboxes[(w_idx, "i")] = inst_cb
                    inst_cb.stateChanged.connect(self._on_any_change)

                wired_w, wired_cb = _centered_checkbox(is_factory, enabled=not is_factory)
                table.setCellWidget(r_idx, 4, wired_w)
                if not is_factory:
                    checkboxes[(w_idx, "w")] = wired_cb
                    wired_cb.stateChanged.connect(self._on_any_change)

        panel_widget = QWidget()
        panel_widget.setObjectName("Panel")
        p_lay = QVBoxLayout(panel_widget)
        p_lay.setContentsMargins(12, 12, 12, 12)
        p_lay.setSpacing(8)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("SectionTitle")
        p_lay.addWidget(title_lbl)
        p_lay.addWidget(table, stretch=1)

        if sash_sensor:
            self._sash_sensor_cb = QCheckBox("Sash Sensor Mounting complete")
            self._sash_sensor_cb.stateChanged.connect(self._on_any_change)
            p_lay.addWidget(self._sash_sensor_cb)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(panel_widget)
        return scroll, checkboxes

    # ── Config & Verification tab ─────────────────────────────────────────────

    def _build_config_verify_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(0, 0, 8, 0)
        v.setSpacing(8)

        # Configuration
        cfg_panel = QWidget()
        cfg_panel.setObjectName("Panel")
        cfg_lay = QVBoxLayout(cfg_panel)
        cfg_lay.setContentsMargins(12, 12, 12, 12)
        cfg_lay.setSpacing(6)
        cfg_lbl = QLabel("Configuration")
        cfg_lbl.setObjectName("SectionTitle")
        cfg_lay.addWidget(cfg_lbl)

        self._cfg_table = QTableWidget(len(CONFIG_ROWS), 3)
        self._cfg_table.setHorizontalHeaderLabels(["Task", "CFM", "Height / Notes"])
        self._cfg_table.verticalHeader().setVisible(False)
        self._cfg_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._cfg_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._cfg_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._cfg_table.setAlternatingRowColors(True)
        ch = self._cfg_table.horizontalHeader()
        ch.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        ch.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        ch.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._cfg_table.setColumnWidth(1, 90)

        self._cfg_cfm:   dict[str, QLineEdit] = {}
        self._cfg_notes: dict[str, QLineEdit] = {}

        for r_idx, (key, label) in enumerate(CONFIG_ROWS):
            self._cfg_table.setRowHeight(r_idx, 42)
            ti = QTableWidgetItem(label)
            ti.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._cfg_table.setItem(r_idx, 0, ti)

            cfm_edit = QLineEdit()
            cfm_edit.setPlaceholderText("CFM")
            cfm_edit.textChanged.connect(self._on_any_change)
            self._cfg_table.setCellWidget(r_idx, 1, cfm_edit)
            self._cfg_cfm[key] = cfm_edit

            notes_edit = QLineEdit()
            notes_edit.setPlaceholderText("Height / Notes")
            notes_edit.textChanged.connect(self._on_any_change)
            self._cfg_table.setCellWidget(r_idx, 2, notes_edit)
            self._cfg_notes[key] = notes_edit

        self._cfg_table.setFixedHeight(
            self._cfg_table.horizontalHeader().height() + len(CONFIG_ROWS) * 42 + 4
        )
        cfg_lay.addWidget(self._cfg_table)
        v.addWidget(cfg_panel)

        # Verification
        vfy_panel = QWidget()
        vfy_panel.setObjectName("Panel")
        vfy_lay = QVBoxLayout(vfy_panel)
        vfy_lay.setContentsMargins(12, 12, 12, 12)
        vfy_lay.setSpacing(6)
        vfy_lbl = QLabel("Verification")
        vfy_lbl.setObjectName("SectionTitle")
        vfy_lay.addWidget(vfy_lbl)

        self._vfy_table = QTableWidget(len(VERIFY_ROWS), 3)
        self._vfy_table.setHorizontalHeaderLabels(["Task", "Result", "Notes"])
        self._vfy_table.verticalHeader().setVisible(False)
        self._vfy_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._vfy_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._vfy_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._vfy_table.setAlternatingRowColors(True)
        vh = self._vfy_table.horizontalHeader()
        vh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        vh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        vh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._vfy_table.setColumnWidth(1, 90)

        self._vfy_result: dict[str, QComboBox] = {}
        self._vfy_notes:  dict[str, QLineEdit] = {}

        for r_idx, (key, label) in enumerate(VERIFY_ROWS):
            self._vfy_table.setRowHeight(r_idx, 42)
            ti = QTableWidgetItem(label)
            ti.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._vfy_table.setItem(r_idx, 0, ti)

            combo = QComboBox()
            combo.addItems(["", "Pass", "Fail", "N/A"])
            combo.currentIndexChanged.connect(self._on_any_change)
            self._vfy_table.setCellWidget(r_idx, 1, combo)
            self._vfy_result[key] = combo

            notes_edit = QLineEdit()
            notes_edit.setPlaceholderText("Notes")
            notes_edit.textChanged.connect(self._on_any_change)
            self._vfy_table.setCellWidget(r_idx, 2, notes_edit)
            self._vfy_notes[key] = notes_edit

        self._vfy_table.setFixedHeight(
            self._vfy_table.horizontalHeader().height() + len(VERIFY_ROWS) * 42 + 4
        )
        vfy_lay.addWidget(self._vfy_table)
        v.addWidget(vfy_panel)
        v.addStretch()

        scroll.setWidget(inner)
        return scroll

    # ── Notes tab ─────────────────────────────────────────────────────────────

    def _build_notes_tab(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("Panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(6)
        lbl = QLabel("Notes")
        lbl.setObjectName("SectionTitle")
        lay.addWidget(lbl)
        self._notes_edit = QPlainTextEdit()
        self._notes_edit.textChanged.connect(self._on_any_change)
        lay.addWidget(self._notes_edit)
        return panel

    # ── Update banner ─────────────────────────────────────────────────────────

    def _build_update_banner(self) -> QWidget:
        banner = QWidget()
        banner.setObjectName("UpdateBanner")
        lay = QHBoxLayout(banner)
        lay.setContentsMargins(12, 6, 12, 6)
        self._update_msg = QLabel("")
        self._update_msg.setObjectName("UpdateMsg")
        lay.addWidget(self._update_msg)
        lay.addStretch()
        whats_new_btn = QPushButton("What's New?")
        whats_new_btn.clicked.connect(self._show_whats_new)
        lay.addWidget(whats_new_btn)
        install_btn = QPushButton("Install & Restart")
        install_btn.setObjectName("InstallBtn")
        install_btn.clicked.connect(self._install_update)
        lay.addWidget(install_btn)
        dismiss_btn = QPushButton("\u2715")
        dismiss_btn.setFixedWidth(32)
        dismiss_btn.clicked.connect(lambda: banner.setVisible(False))
        lay.addWidget(dismiss_btn)
        return banner

    # ── Tree helpers ──────────────────────────────────────────────────────────

    def _refresh_tree(self, select_id: Optional[str] = None) -> None:
        """Rebuild the job/checkout tree, then re-select select_id if given."""
        self._tree.blockSignals(True)
        self._tree.clear()

        job_font = QFont()
        job_font.setBold(True)
        job_font.setPointSize(10)

        for job in self._store.all_jobs():
            job_item = QTreeWidgetItem([_job_label(job)])
            job_item.setFont(0, job_font)
            job_item.setData(0, self._ROLE, ("job", job.id))

            for record in self._store.records_for_job(job.id):
                child = QTreeWidgetItem([record.valve_tag or "(No Tag)"])
                child.setData(0, self._ROLE, ("checkout", record.id))
                self._apply_item_color(child, record.pass_fail)
                job_item.addChild(child)

            self._tree.addTopLevelItem(job_item)
            job_item.setExpanded(True)

        self._tree.blockSignals(False)

        if select_id:
            self._select_by_id(select_id)
        elif self._tree.topLevelItemCount() == 0:
            self._load_record(None)

    def _select_by_id(self, target_id: str) -> None:
        for i in range(self._tree.topLevelItemCount()):
            job_item = self._tree.topLevelItem(i)
            _, jid = job_item.data(0, self._ROLE)
            if jid == target_id:
                self._tree.setCurrentItem(job_item)
                return
            for j in range(job_item.childCount()):
                child = job_item.child(j)
                _, cid = child.data(0, self._ROLE)
                if cid == target_id:
                    self._tree.setCurrentItem(child)
                    return

    def _apply_item_color(self, item: QTreeWidgetItem, pass_fail: str) -> None:
        if pass_fail == "Pass":
            item.setForeground(0, QBrush(_PASS_COLOR))
        elif pass_fail == "Fail":
            item.setForeground(0, QBrush(_FAIL_COLOR))
        else:
            item.setForeground(0, QBrush())  # reset to palette default

    def _selected_job_id(self) -> Optional[str]:
        """Return the job_id of whatever is currently selected in the tree."""
        items = self._tree.selectedItems()
        if not items:
            return None
        kind, id_ = items[0].data(0, self._ROLE)
        if kind == "job":
            return id_
        rec = self._store.get(id_)
        return rec.job_id if rec else None

    # ── Tree signals ──────────────────────────────────────────────────────────

    def _on_tree_changed(
        self,
        current: Optional[QTreeWidgetItem],
        _previous: Optional[QTreeWidgetItem],
    ) -> None:
        if current is None:
            self._load_record(None)
            self._new_checkout_btn.setEnabled(False)
            return

        kind, id_ = current.data(0, self._ROLE)
        self._new_checkout_btn.setEnabled(True)

        if kind == "job":
            job = self._store.get_job(id_)
            self._load_record(None)
            if job:
                self._hdr_tag.setText(_job_label(job))
                records  = self._store.records_for_job(job.id)
                total    = len(records)
                passes   = sum(1 for r in records if r.pass_fail == "Pass")
                fails    = sum(1 for r in records if r.pass_fail == "Fail")
                self._hdr_sub.setText(
                    f"{total} checkout{'s' if total != 1 else ''}   \u2022   "
                    f"{passes} passed   \u2022   {fails} failed"
                )
        else:
            self._load_record(self._store.get(id_))

    def _on_tree_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if not item:
            return
        kind, id_ = item.data(0, self._ROLE)
        menu = QMenu(self)

        if kind == "job":
            add_act = menu.addAction("Add Checkout to Job")
            menu.addSeparator()
            export_job_act = menu.addAction("Export All Checkouts to Excel\u2026")
            menu.addSeparator()
            del_act = menu.addAction("Delete Job")
            action = menu.exec(self._tree.mapToGlobal(pos))
            if action == add_act:
                job = self._store.get_job(id_)
                if job:
                    self._open_new_checkout_for_job(job)
            elif action == export_job_act:
                self._export_job(id_)
            elif action == del_act:
                self._delete_job(id_)
        else:
            export_act = menu.addAction("Export to Excel\u2026")
            menu.addSeparator()
            del_act = menu.addAction("Delete Checkout")
            action = menu.exec(self._tree.mapToGlobal(pos))
            if action == export_act:
                self._export_checkout(id_)
            elif action == del_act:
                self._delete_checkout(id_)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_new_job(self) -> None:
        dlg = NewJobDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            job = dlg.get_job()
            self._store.add_job(job)
            self._refresh_tree(select_id=job.id)

    def _on_new_checkout(self) -> None:
        job_id = self._selected_job_id()
        if not job_id:
            QMessageBox.information(self, "No Job Selected",
                                    "Select or create a job first, then add a checkout.")
            return
        job = self._store.get_job(job_id)
        if job:
            self._open_new_checkout_for_job(job)

    def _open_new_checkout_for_job(self, job: Job) -> None:
        dlg = NewCheckoutDialog(job, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            record = dlg.get_record()
            self._store.add(record)
            self._refresh_tree(select_id=record.id)

    def _delete_job(self, job_id: str) -> None:
        job = self._store.get_job(job_id)
        if not job:
            return
        count = len(self._store.records_for_job(job_id))
        msg = (
            f"Delete job '{_job_label(job)}'?\n\n"
            f"This will also delete {count} checkout record{'s' if count != 1 else ''}."
        )
        if QMessageBox.question(
            self, "Delete Job", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self._store.delete_job(job_id)
            if self._current_id and not self._store.get(self._current_id):
                self._current_id = None
            self._refresh_tree()
            self._load_record(None)

    def _delete_checkout(self, record_id: str) -> None:
        rec = self._store.get(record_id)
        tag = rec.valve_tag if rec else "this record"
        if QMessageBox.question(
            self, "Delete Checkout",
            f"Delete checkout record '{tag}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self._store.delete(record_id)
            if self._current_id == record_id:
                self._current_id = None
            self._refresh_tree()
            self._load_record(None)

    # ── Export ────────────────────────────────────────────────────────────────

    def _on_export_current(self) -> None:
        if self._current_id is None:
            QMessageBox.information(self, "No Checkout Selected",
                                    "Select a checkout record first, then export.")
            return
        self._export_checkout(self._current_id)

    def _on_export_job(self) -> None:
        job_id = self._selected_job_id()
        if not job_id:
            QMessageBox.information(self, "No Job Selected",
                                    "Select a job first, then export.")
            return
        self._export_job(job_id)

    def _export_checkout(self, record_id: str) -> None:
        record = self._store.get(record_id)
        if not record:
            return
        default_name = f"{record.valve_tag or 'Checkout'}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Checkout", default_name,
            "Excel Workbook (*.xlsx)"
        )
        if not path:
            return
        try:
            export_records([record], path)
            QMessageBox.information(self, "Export Complete",
                                    f"Exported to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def _export_job(self, job_id: str) -> None:
        records = self._store.records_for_job(job_id)
        if not records:
            QMessageBox.information(self, "No Checkouts",
                                    "This job has no checkout records to export.")
            return
        job = self._store.get_job(job_id)
        default_name = f"{job.job_number or job.job_name or 'Job'} Checkouts.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export All Checkouts", default_name,
            "Excel Workbook (*.xlsx)"
        )
        if not path:
            return
        try:
            export_records(records, path)
            QMessageBox.information(
                self, "Export Complete",
                f"Exported {len(records)} checkout{'s' if len(records) != 1 else ''} to:\n{path}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    # ── Load / save record ────────────────────────────────────────────────────

    def _load_record(self, record: Optional[ValveCheckout]) -> None:
        self._loading = True
        self._current_id = record.id if record else None
        self._tabs.setEnabled(record is not None)

        if not record:
            self._hdr_tag.setText("Select a job or checkout")
            self._hdr_sub.setText("")
            self._hdr_badge.setText("")
            self._hdr_badge.setStyleSheet("")
            self._loading = False
            return

        # Header
        self._hdr_tag.setText(record.valve_tag or "(No Tag)")
        parts = []
        if record.project:
            parts.append(record.project)
        if record.ats_job_number:
            parts.append(f"Job #{record.ats_job_number}")
        if record.technician:
            parts.append(f"Tech: {record.technician}")
        if record.date:
            parts.append(record.date)
        self._hdr_sub.setText("   \u2022   ".join(parts))
        self._refresh_badge(record.pass_fail)

        # General
        self._f_valve_tag.setText(record.valve_tag)
        self._f_project.setText(record.project)
        self._f_job_number.setText(record.ats_job_number)
        self._f_technician.setText(record.technician)
        self._f_description.setText(record.description)
        self._f_model.setText(record.model)
        if record.date:
            d = QDate.fromString(record.date, "yyyy-MM-dd")
            if d.isValid():
                self._f_date.setDate(d)
        self._f_pass_fail.setCurrentText(record.pass_fail)
        self._f_emer_min.setText(record.emer_min)
        self._f_valve_min_sp.setText(record.valve_min_sp)
        self._f_valve_max_sp.setText(record.valve_max_sp)

        # Wiring
        w = record.wiring
        for (idx, fld), cb in self._phoenix_cbs.items():
            cb.blockSignals(True)
            cb.setChecked(w.get(f"p_{idx}_{fld}", False))
            cb.blockSignals(False)
        for (idx, fld), cb in self._bb_cbs.items():
            cb.blockSignals(True)
            cb.setChecked(w.get(f"b_{idx}_{fld}", False))
            cb.blockSignals(False)
        self._sash_sensor_cb.blockSignals(True)
        self._sash_sensor_cb.setChecked(record.sash_sensor_mounted)
        self._sash_sensor_cb.blockSignals(False)

        # Config
        cfg = record.config
        for key, _ in CONFIG_ROWS:
            self._cfg_cfm[key].blockSignals(True)
            self._cfg_cfm[key].setText(cfg.get(f"{key}_cfm", ""))
            self._cfg_cfm[key].blockSignals(False)
            self._cfg_notes[key].blockSignals(True)
            self._cfg_notes[key].setText(cfg.get(f"{key}_notes", ""))
            self._cfg_notes[key].blockSignals(False)

        # Verification
        vfy = record.verification
        for key, _ in VERIFY_ROWS:
            self._vfy_result[key].blockSignals(True)
            self._vfy_result[key].setCurrentText(vfy.get(f"{key}_result", ""))
            self._vfy_result[key].blockSignals(False)
            self._vfy_notes[key].blockSignals(True)
            self._vfy_notes[key].setText(vfy.get(f"{key}_notes", ""))
            self._vfy_notes[key].blockSignals(False)

        # Notes
        self._notes_edit.blockSignals(True)
        self._notes_edit.setPlainText(record.notes)
        self._notes_edit.blockSignals(False)

        self._loading = False

    def _refresh_badge(self, pf: str) -> None:
        if pf == "Pass":
            self._hdr_badge.setText("PASS")
            self._hdr_badge.setStyleSheet(
                "background:#2d8a4a; color:white; border-radius:8px;"
                "font-weight:700; font-size:11pt;"
            )
        elif pf == "Fail":
            self._hdr_badge.setText("FAIL")
            self._hdr_badge.setStyleSheet(
                "background:#c0392b; color:white; border-radius:8px;"
                "font-weight:700; font-size:11pt;"
            )
        else:
            self._hdr_badge.setText("")
            self._hdr_badge.setStyleSheet("")

    def _on_any_change(self) -> None:
        if self._loading or self._current_id is None:
            return
        self._save_timer.start()

    def _save_current(self) -> None:
        if self._current_id is None:
            return
        record = self._store.get(self._current_id)
        if record is None:
            return
        self._loading = True

        record.valve_tag      = self._f_valve_tag.text().strip()
        record.project        = self._f_project.text().strip()
        record.ats_job_number = self._f_job_number.text().strip()
        record.technician     = self._f_technician.text().strip()
        record.description    = self._f_description.text().strip()
        record.model          = self._f_model.text().strip()
        record.date           = self._f_date.date().toString("yyyy-MM-dd")
        record.pass_fail      = self._f_pass_fail.currentText()
        record.emer_min       = self._f_emer_min.text().strip()
        record.valve_min_sp   = self._f_valve_min_sp.text().strip()
        record.valve_max_sp   = self._f_valve_max_sp.text().strip()

        w: dict = {}
        for (idx, fld), cb in self._phoenix_cbs.items():
            w[f"p_{idx}_{fld}"] = cb.isChecked()
        for (idx, fld), cb in self._bb_cbs.items():
            w[f"b_{idx}_{fld}"] = cb.isChecked()
        record.wiring = w
        record.sash_sensor_mounted = self._sash_sensor_cb.isChecked()

        cfg: dict = {}
        for key, _ in CONFIG_ROWS:
            cfg[f"{key}_cfm"]   = self._cfg_cfm[key].text()
            cfg[f"{key}_notes"] = self._cfg_notes[key].text()
        record.config = cfg

        vfy: dict = {}
        for key, _ in VERIFY_ROWS:
            vfy[f"{key}_result"] = self._vfy_result[key].currentText()
            vfy[f"{key}_notes"]  = self._vfy_notes[key].text()
        record.verification = vfy

        record.notes = self._notes_edit.toPlainText()

        self._store.update(record)

        # Update tree item label + color in-place (no full rebuild)
        for i in range(self._tree.topLevelItemCount()):
            job_item = self._tree.topLevelItem(i)
            for j in range(job_item.childCount()):
                child = job_item.child(j)
                _, cid = child.data(0, self._ROLE)
                if cid == self._current_id:
                    child.setText(0, record.valve_tag or "(No Tag)")
                    self._apply_item_color(child, record.pass_fail)
                    break

        # Refresh header live
        self._hdr_tag.setText(record.valve_tag or "(No Tag)")
        parts = []
        if record.project:
            parts.append(record.project)
        if record.ats_job_number:
            parts.append(f"Job #{record.ats_job_number}")
        if record.technician:
            parts.append(f"Tech: {record.technician}")
        if record.date:
            parts.append(record.date)
        self._hdr_sub.setText("   \u2022   ".join(parts))
        self._refresh_badge(record.pass_fail)

        self._loading = False

    # ── Misc actions ──────────────────────────────────────────────────────────

    def _show_about(self) -> None:
        QMessageBox.information(
            self, f"About {self.APP_NAME}",
            f"{self.APP_NAME}\nVersion {__version__}\n\nBuilt for ATS Inc.",
        )

    # ── Dark / light mode ─────────────────────────────────────────────────────

    def _toggle_dark_mode(self) -> None:
        dark = self._dark_mode_action.isChecked()
        app: QApplication = QApplication.instance()  # type: ignore[assignment]
        if app:
            apply_dark_theme(app) if dark else apply_light_theme(app)
        QSettings("ATS Inc", self.APP_NAME).setValue("darkMode", "true" if dark else "false")

    def _restore_settings(self) -> None:
        dark_on = QSettings("ATS Inc", self.APP_NAME).value("darkMode", "true") != "false"
        app: QApplication = QApplication.instance()  # type: ignore[assignment]
        if app:
            apply_dark_theme(app) if dark_on else apply_light_theme(app)

    def closeEvent(self, event) -> None:
        QSettings("ATS Inc", self.APP_NAME).setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    # ── Auto-updater ──────────────────────────────────────────────────────────

    def _check_for_updates(self) -> None:
        self._update_checker = _UpdateChecker()
        self._update_checker.found.connect(self._on_update_found)
        self._update_checker.start()

    def _on_update_found(self, info: updater.UpdateInfo) -> None:
        self._update_info = info
        self._update_msg.setText(
            f"Update available \u2014 v{info.latest_version} is ready. "
            f"You're on v{info.current_version}."
        )
        self._update_banner.setVisible(True)

    def _show_whats_new(self) -> None:
        if not self._update_info:
            return
        QMessageBox.information(
            self,
            f"What's New in v{self._update_info.latest_version}",
            self._update_info.release_notes or "No release notes provided.",
        )

    def _install_update(self) -> None:
        if not self._update_info:
            return
        try:
            updater.download_and_apply(self._update_info)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Update Failed", str(exc))


# ── Themes ────────────────────────────────────────────────────────────────────

def apply_light_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in [
        (QPalette.ColorRole.Window,          QColor(210, 212, 218)),
        (QPalette.ColorRole.WindowText,      QColor(25, 25, 25)),
        (QPalette.ColorRole.Base,            QColor(225, 227, 232)),
        (QPalette.ColorRole.AlternateBase,   QColor(200, 202, 208)),
        (QPalette.ColorRole.ToolTipBase,     QColor(255, 255, 220)),
        (QPalette.ColorRole.ToolTipText,     QColor(20, 20, 20)),
        (QPalette.ColorRole.Text,            QColor(25, 25, 25)),
        (QPalette.ColorRole.Button,          QColor(195, 198, 206)),
        (QPalette.ColorRole.ButtonText,      QColor(25, 25, 25)),
        (QPalette.ColorRole.BrightText,      QColor(180, 0, 0)),
        (QPalette.ColorRole.Highlight,       QColor(72, 124, 255)),
        (QPalette.ColorRole.HighlightedText, QColor(255, 255, 255)),
        (QPalette.ColorRole.Link,            QColor(0, 90, 200)),
    ]:
        palette.setColor(role, color)
    app.setPalette(palette)
    app.setStyleSheet("""
        QWidget { font-family: Segoe UI, Arial, sans-serif; font-size: 11pt; }
        QMainWindow, QMenuBar, QMenu, QStatusBar { background:#d2d4da; color:#191919; }
        QMenuBar::item:selected, QMenu::item:selected { background:#487cff; color:white; }
        QTabWidget::pane { border:none; }
        QTabBar::tab {
            background:#c3c6ce; border:1px solid #a8acb8; border-bottom:none;
            border-radius:6px 6px 0 0; padding:6px 18px; color:#191919;
        }
        QTabBar::tab:selected { background:#d2d4da; font-weight:600; }
        QTabBar::tab:hover:!selected { background:#b2b6c2; }
        #Panel, #StatCard {
            background:rgba(220,222,228,200); border:1px solid #b0b4be; border-radius:14px;
        }
        QLabel#ProjectTitle    { font-size:14pt; font-weight:700; color:#111111; }
        QLabel#ProjectSubtitle { color:#555b66; font-size:10pt; }
        QLabel#SectionTitle    { font-size:12pt; font-weight:600; color:#191919; }
        QPushButton, QToolButton {
            background:#c3c6ce; border:1px solid #a8acb8; border-radius:10px;
            padding:6px 14px; color:#191919;
        }
        QPushButton:hover, QToolButton:hover { background:#b2b6c2; }
        QPushButton:pressed, QToolButton:pressed { background:#a0a4b0; }
        QPushButton:disabled { background:#d8dae0; color:#a0a4b0; }
        QLineEdit, QPlainTextEdit, QComboBox, QDateEdit {
            background:#e1e3e8; border:1px solid #a8acb8; border-radius:10px;
            padding:6px 8px; color:#191919; selection-background-color:#487cff;
        }
        QFormLayout QLabel { color:#555b66; font-size:10pt; }
        QTreeWidget {
            background:transparent; border:1px solid #a8acb8; border-radius:10px;
            padding:4px; color:#191919; outline:none;
        }
        QTreeWidget::item { border-radius:6px; padding:5px 8px; margin:1px 0; }
        QTreeWidget::item:selected { background:#487cff; color:white; }
        QTreeWidget::item:hover:!selected { background:#c3c6ce; }
        QTreeView::branch { background:transparent; }
        QTableWidget {
            background:transparent; border:1px solid #a8acb8; border-radius:10px;
            padding:4px; color:#191919; gridline-color:#c8ccd4;
        }
        QTableWidget::item { background:rgba(215,217,223,180); padding:3px 6px; border:none; }
        QTableWidget::item:alternate { background:rgba(200,202,208,180); }
        QHeaderView::section {
            background:rgba(195,198,206,220); color:#191919; padding:6px 8px;
            border:none; border-right:1px solid #a8acb8; border-bottom:1px solid #a8acb8;
            font-weight:600;
        }
        QScrollBar:vertical { width:8px; background:transparent; }
        QScrollBar::handle:vertical { background:#b0b4be; border-radius:4px; min-height:20px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        #UpdateBanner { background:rgba(195,228,205,220); border-top:1px solid #5cb87a; }
        #UpdateBanner QLabel#UpdateMsg { color:#1a6830; font-weight:600; }
        #InstallBtn { background:#2d8a4a; border:1px solid #3daa5a; color:white; font-weight:700; }
        #InstallBtn:hover { background:#3daa5a; }
    """)


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in [
        (QPalette.ColorRole.Window,          QColor(28, 28, 28)),
        (QPalette.ColorRole.WindowText,      QColor(230, 230, 230)),
        (QPalette.ColorRole.Base,            QColor(18, 18, 18)),
        (QPalette.ColorRole.AlternateBase,   QColor(35, 35, 35)),
        (QPalette.ColorRole.ToolTipBase,     QColor(240, 240, 240)),
        (QPalette.ColorRole.ToolTipText,     QColor(20, 20, 20)),
        (QPalette.ColorRole.Text,            QColor(230, 230, 230)),
        (QPalette.ColorRole.Button,          QColor(45, 45, 45)),
        (QPalette.ColorRole.ButtonText,      QColor(235, 235, 235)),
        (QPalette.ColorRole.BrightText,      QColor(255, 90, 90)),
        (QPalette.ColorRole.Highlight,       QColor(72, 124, 255)),
        (QPalette.ColorRole.HighlightedText, QColor(255, 255, 255)),
        (QPalette.ColorRole.Link,            QColor(102, 169, 255)),
    ]:
        palette.setColor(role, color)
    app.setPalette(palette)
    app.setStyleSheet("""
        QWidget { font-family: Segoe UI, Arial, sans-serif; font-size: 11pt; }
        QMainWindow, QMenuBar, QMenu, QStatusBar { background:#1c1c1c; color:#e8e8e8; }
        QMenuBar::item:selected, QMenu::item:selected { background:#487cff; color:white; }
        QTabWidget::pane { border:none; }
        QTabBar::tab {
            background:#2d2d2d; border:1px solid #404040; border-bottom:none;
            border-radius:6px 6px 0 0; padding:6px 18px;
        }
        QTabBar::tab:selected { background:#1c1c1c; font-weight:600; }
        QTabBar::tab:hover:!selected { background:#383838; }
        #Panel, #StatCard {
            background:rgba(38,38,38,160); border:1px solid #3a3a3a; border-radius:14px;
        }
        QLabel#ProjectTitle    { font-size:14pt; font-weight:700; }
        QLabel#ProjectSubtitle { color:#999999; font-size:10pt; }
        QLabel#SectionTitle    { font-size:12pt; font-weight:600; }
        QPushButton, QToolButton {
            background:#383838; border:1px solid #505050; border-radius:10px; padding:6px 14px;
        }
        QPushButton:hover, QToolButton:hover { background:#454545; }
        QPushButton:pressed, QToolButton:pressed { background:#2a2a2a; }
        QPushButton:disabled { background:#2a2a2a; color:#555555; border-color:#383838; }
        QLineEdit, QPlainTextEdit, QComboBox, QDateEdit {
            background:#121212; border:1px solid #404040; border-radius:10px;
            padding:6px 8px; color:#ececec; selection-background-color:#487cff;
        }
        QFormLayout QLabel { color:#aaaaaa; font-size:10pt; }
        QTreeWidget {
            background:transparent; border:1px solid #404040; border-radius:10px;
            padding:4px; color:#ececec; outline:none;
        }
        QTreeWidget::item { border-radius:6px; padding:5px 8px; margin:1px 0; }
        QTreeWidget::item:selected { background:#2d4c8f; color:white; }
        QTreeWidget::item:hover:!selected { background:#383838; }
        QTreeView::branch { background:transparent; }
        QTableWidget {
            background:transparent; border:1px solid #404040; border-radius:10px;
            padding:4px; color:#ececec; gridline-color:#333333;
        }
        QTableWidget::item { background:rgba(25,25,25,140); padding:3px 6px; border:none; }
        QTableWidget::item:alternate { background:rgba(35,35,35,140); }
        QHeaderView::section {
            background:rgba(40,40,40,180); color:#e0e0e0; padding:6px 8px;
            border:none; border-right:1px solid #3a3a3a; border-bottom:1px solid #3a3a3a;
            font-weight:600;
        }
        QScrollBar:vertical { width:8px; background:transparent; }
        QScrollBar::handle:vertical { background:#555555; border-radius:4px; min-height:20px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        #UpdateBanner { background:rgba(30,60,40,220); border-top:1px solid #2d6a3f; }
        #UpdateBanner QLabel#UpdateMsg { color:#6ee7a0; font-weight:600; }
        #InstallBtn { background:#1e5c32; border:1px solid #2d8a4a; color:white; font-weight:700; }
        #InstallBtn:hover { background:#2d8a4a; }
    """)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Phoenix Valve Checkout Tool")
    app.setOrganizationName("ATS Inc")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
