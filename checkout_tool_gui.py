"""
checkout_tool_gui.py — Phoenix Valve Checkout Tool
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDate, Qt, QSettings, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QIcon, QIntValidator, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateEdit, QDialog,
    QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSpinBox, QSplitter,
    QStackedWidget, QTabWidget, QTableWidget, QTableWidgetItem, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from checkout_tool_backend import CheckoutStore, Job, ValveCheckout, DATA_FILE
from checkout_export import export_records, NOTES_MAX_LINES
from version import __version__
import updater

# ── Phoenix component helpers ─────────────────────────────────────────────────

class PrimaryButton(QPushButton):
    """Red primary-action button with pointer cursor and consistent height."""
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class SecondaryButton(QPushButton):
    """Blue secondary-action button."""
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("secondaryButton")
        self.setMinimumHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class TertiaryButton(QPushButton):
    """Outline tertiary button for low-emphasis actions."""
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("tertiaryButton")
        self.setMinimumHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class _PhoenixTable(QTableWidget):
    """Read-only data table with standard Phoenix styling defaults."""
    def __init__(self, rows: int, cols: int, parent=None):
        super().__init__(rows, cols, parent)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAlternatingRowColors(True)


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
    ("TB3 \u2014 INTERNAL  (Factory Wired \u2014 Do Not Modify)",  2, "GREEN / VPOT",         "Valve Position Feedback",        True),
    ("TB3 \u2014 INTERNAL  (Factory Wired \u2014 Do Not Modify)",  3, "BLACK / VPOT",         "Valve Position Feedback",        True),
    ("TB3 \u2014 INTERNAL  (Factory Wired \u2014 Do Not Modify)",  4, "PRESSURE SW (R)",      "Pressure Switch Dry Contact",    True),
    ("TB3 \u2014 INTERNAL  (Factory Wired \u2014 Do Not Modify)",  5, "PRESSURE SW (B)",      "Pressure Switch Dry Contact",    True),
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

# ── CSCP ACM (Actuator Control Module) wiring ─────────────────────────────────
ACM_WIRING: list[tuple] = [
    ("Connector/Terminal P10",   1, "EGND (Jumper \u2192 Pin 2)", "Main Power Input",          False),
    ("Connector/Terminal P10",   2, "V0 (Jumper \u2192 Pin 1)",   "",                          False),
    ("Connector/Terminal P10",   3, "+24VAC",                      "",                          False),
    ("Connector/Terminal P20",   4, "M1",                          "Actuator Output",           True),
    ("Connector/Terminal P20",   5, "M2",                          "",                          True),
    ("Connector/Terminal P30",  13, "NC or Not Used",              "DP Sensor",                 True),
    ("Connector/Terminal P30",  14, "+3V3",                        "",                          True),
    ("Connector/Terminal P30",  15, "Ground",                      "",                          True),
    ("Connector/Terminal P30",  16, "Analog Input",                "",                          True),
    ("Connector/Terminal P40",  18, "DA+",                         "T1L Port A",                False),
    ("Connector/Terminal P40",  19, "DA\u2212",                    "",                          False),
    ("Connector/Terminal P40",  20, "EGND",                        "",                          False),
    ("Connector/Terminal P50",  21, "DA+",                         "T1L Port B",                False),
    ("Connector/Terminal P50",  22, "DA\u2212",                    "",                          False),
    ("Connector/Terminal P50",  23, "EGND",                        "",                          False),
    ("Connector/Terminal P60",  24, "D\u2212",                     "RS485",                     False),
    ("Connector/Terminal P60",  25, "D+",                          "",                          False),
    ("Connector/Terminal P60",  26, "COM (GND)",                   "",                          False),
    ("Connector/Terminal P70",  27, "UIO_1  (Sash RED)",           "UIO 1 & 2",                 False),
    ("Connector/Terminal P70",  28, "GND  (Sash BLACK)",           "",                          False),
    ("Connector/Terminal P70",  29, "UIO_2",                       "",                          False),
    ("Connector/Terminal P70",  30, "GND",                         "",                          False),
    ("Connector/Terminal P80",  27, "5V",                          "Vpot",                      True),
    ("Connector/Terminal P80",  28, "VPOT",                        "",                          True),
    ("Connector/Terminal P80",  29, "GND",                         "",                          True),
]

# ── CSCP DHV Black Box wiring ──────────────────────────────────────────────────
DHV_BB_WIRING: list[tuple] = [
    ("TB1 \u2014 POWER IN",    1, "L1 +",          "24 VAC",                              False),
    ("TB1 \u2014 POWER IN",    2, "GROUND",         "",                                    False),
    ("TB1 \u2014 POWER IN",    3, "L2 \u2212",      "24 VAC",                              False),
    ("TB2 \u2014 OUTPUTS",     1, "V OUT",           "Lands on Pin 27 on Phoenix Valve",    False),
    ("TB2 \u2014 OUTPUTS",     2, "Ground",          "Lands on Pin 28 on Phoenix Valve",    False),
    ("TB3 \u2014 INPUTS",      1, "IN-1 +",          "Vertical Sash Sensor",                False),
    ("TB3 \u2014 INPUTS",      2, "IN-1 \u2212",     "Vertical Sash Sensor",                False),
    ("TB3 \u2014 INPUTS",      3, "24 VAC POWER",    "",                                    False),
    ("TB3 \u2014 INPUTS",      4, "HOT",             "",                                    False),
    ("TB3 \u2014 INPUTS",      5, "GND",             "",                                    False),
    ("UIO 1",                  1, "Signal",           "",                                    False),
    ("UIO 1",                  2, "GND",              "",                                    False),
    ("UIO 2",                  1, "Signal",           "",                                    False),
    ("UIO 2",                  2, "GND",              "",                                    False),
    ("UI 1",                   1, "Signal",           "",                                    False),
    ("UI 1",                   2, "GND",              "",                                    False),
    ("UI 2",                   1, "Signal",           "",                                    False),
    ("UI 2",                   2, "GND",              "",                                    False),
    ("DO SWITCH",              1, "DO +",             "",                                    False),
    ("DO SWITCH",              2, "DO \u2212",        "",                                    False),
    ("MSTP",                   1, "RS485 +",          "",                                    False),
    ("MSTP",                   2, "RS485 \u2212",     "",                                    False),
]

# ── CSCP PBC Room wiring — left panel (TB1 INPUTS / DO Relay / DO SSR / UIO) ──
PBC_WIRING_LEFT: list[tuple] = [
    ("TB1 \u2014 24V Power",    1, "Bldg Earth GND",  "Building Earth Ground",          False),
    ("TB1 \u2014 24V Power",    2, "V0",               "24 VAC/VDC",                     False),
    ("TB1 \u2014 24V Power",    3, "24 VAC/VDC",       "",                               False),
    ("DO Relay",                4, "NC1",               "Normally Closed 1",              False),
    ("DO Relay",                5, "NO1",               "Normally Open 1",                False),
    ("DO Relay",                6, "IN1",               "Input Power 1",                  False),
    ("DO Relay",                7, "NC2",               "Normally Closed 2",              False),
    ("DO Relay",                8, "NO2",               "Normally Open 2",                False),
    ("DO Relay",                9, "IN2",               "Input Power 2",                  False),
    ("DO Relay",               10, "NC3",               "Normally Closed 3",              False),
    ("DO Relay",               11, "NO3",               "Normally Open 3",                False),
    ("DO Relay",               12, "IN3",               "Input Power 3",                  False),
    ("DO Relay",               13, "NC4",               "Normally Closed 4",              False),
    ("DO Relay",               14, "NO4",               "Normally Open 4",                False),
    ("DO Relay",               15, "IN4",               "Input Power 4",                  False),
    ("DO SSR",                 16, "AUX OUT",           "24 VAC/VDC Auxiliary Output",    False),
    ("DO SSR",                 17, "SRIN",              "24 VAC/VDC Aux Input",           True),
    ("DO SSR",                 18, "SR1",               "SSR1 Output",                    False),
    ("DO SSR",                 19, "C",                 "Common",                         False),
    ("DO SSR",                 20, "SR2",               "SSR2 Output",                    False),
    ("DO SSR",                 21, "SR3",               "SSR3 Output",                    False),
    ("DO SSR",                 22, "C",                 "Common",                         False),
    ("DO SSR",                 23, "SR4",               "SSR4 Output",                    False),
    ("I/O",                    24, "???",               "",                               False),
    ("I/O",                    25, "???",               "",                               False),
    ("I/O",                    26, "???",               "",                               False),
    ("I/O",                    27, "???",               "",                               False),
    ("I/O",                    28, "???",               "",                               False),
    ("I/O",                    29, "???",               "",                               False),
    ("I/O",                    30, "???",               "",                               False),
    ("I/O",                    31, "???",               "",                               False),
    ("UIO",                    32, "IO13",              "Universal Input/Output 13",       False),
    ("UIO",                    33, "C",                 "Common",                         False),
    ("UIO",                    34, "IO14",              "Universal Input/Output 14",       False),
    ("UIO",                    35, "IO15",              "Universal Input/Output 15",       False),
    ("UIO",                    36, "C",                 "Common",                         False),
    ("UIO",                    37, "IO16",              "Universal Input/Output 16",       False),
    ("UIO",                    38, "24 VDC OUT",        "Auxiliary Power Output",          False),
]

# ── CSCP PBC Room wiring — right panel (Power / Comm / UIO) ───────────────────
PBC_WIRING_RIGHT: list[tuple] = [
    ("TB1 \u2014 POWER IN",    39, "???",               "",                               False),
    ("TB1 \u2014 POWER IN",    40, "???",               "",                               False),
    ("TB1 \u2014 POWER IN",    41, "???",               "",                               False),
    ("BACnet MS/TP",           42, "+",                 "BACnet MS/TP Positive",           False),
    ("BACnet MS/TP",           43, "\u2212",            "BACnet MS/TP Negative",           False),
    ("BACnet MS/TP",           44, "SHLD",              "BACnet MS/TP Shield",             False),
    ("RS485",                  45, "+",                 "RS485 Modbus Positive",           False),
    ("RS485",                  46, "\u2212",            "RS485 Modbus Negative",           False),
    ("RS485",                  47, "COM",               "Shield Termination",              False),
    ("Power 24",               48, "24 VAC",            "24 VAC Power Input Voltage",      False),
    ("Power 24",               49, "V0",                "24 VAC Power Input Voltage",      False),
    ("SYLK Bus",               50, "WM1",               "Sylk Bus",                        False),
    ("SYLK Bus",               51, "WM2",               "Sylk Bus",                        False),
    ("UIO",                    52, "IO1",               "Universal Input/Output 1",        False),
    ("UIO",                    53, "C",                 "Common",                          False),
    ("UIO",                    54, "IO2",               "Universal Input/Output 2",        False),
    ("UIO",                    55, "IO3",               "Universal Input/Output 3",        False),
    ("UIO",                    56, "C",                 "Common",                          False),
    ("UIO",                    57, "IO4",               "Universal Input/Output 4",        False),
    ("UIO",                    58, "IO5",               "Universal Input/Output 5",        False),
    ("UIO",                    59, "C",                 "Common",                          False),
    ("UIO",                    60, "IO6",               "Universal Input/Output 6",        False),
    ("UIO",                    61, "IO7",               "Universal Input/Output 7",        False),
    ("UIO",                    62, "C",                 "Common",                          False),
    ("UIO",                    63, "IO8",               "Universal Input/Output 8",        False),
    ("UIO",                    64, "C",                 "Common",                          False),
    ("UIO",                    65, "23 VDC OUT",        "Auxiliary Power Output",          False),
    ("UIO",                    66, "IO9",               "Universal Input/Output 9",        False),
    ("UIO",                    67, "C",                 "Common",                          False),
    ("UIO",                    68, "IO10",              "Universal Input/Output 10",       False),
    ("UIO",                    69, "IO11",              "Universal Input/Output 11",       False),
    ("UIO",                    70, "C",                 "Common",                          False),
    ("UIO",                    71, "IO12",              "Universal Input/Output 12",       False),
    ("UIO",                    72, "24 VDC OUT",        "Auxiliary Power Output",          False),
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

_NOTES_TEMPLATES: list[tuple[str, str]] = [
    ("— Insert snippet —", ""),
    ("All verified",              "All points verified. Clean install."),
    ("Standard commissioning",   "Standard commissioning complete. All wiring confirmed."),
    ("BACnet confirmed",         "BACnet communication confirmed at controller."),
    ("Low flow verified",        "Low flow alarm triggered and verified."),
    ("Sash sensor OK",           "Sash sensor calibrated and verified."),
    ("JAM alarm failed",         "Unit failed JAM alarm test. Contractor to re-check actuator wiring."),
    ("Not yet commissioned",     "Wiring complete. Unit not yet commissioned — pending controls startup."),
    ("Emergency exhaust OK",     "Emergency exhaust override verified from BAS."),
    ("RS485 issue",              "BACnet MS/TP communication not established. Verify device address and baud rate."),
    ("Pending sash calibration", "Sash sensor installed. Calibration pending — coordinate with hood manufacturer."),
]

# ── Embedded BACnet points list data ─────────────────────────────────────────

_POINTS_HEADERS     = ["Type", "ID", "Name", "Unit", "Function", "Access"]
_PBC_POINTS_HEADERS = ["Type", "ID", "Name", "Category", "Unit", "Access"]

# RPI — (Type, ID, Name, Unit, Function, Access)
_RPI_ROWS: list[tuple] = [
    ("AI",   1,       "AI_UI1Pcnt",                  "%",       "Live",    "R"),
    ("AI",   2,       "AI_UI2Pcnt",                  "%",       "Live",    "R"),
    ("AV",   1,       "AV_Pressure",                 "in.wc.",  "Live",    "R"),
    ("AV",   2,       "AV_UIO1Pcnt",                 "%",       "Live",    "R"),
    ("AV",   3,       "AV_UIO2Pcnt",                 "%",       "Live",    "R"),
    ("AV",   4,       "AV_DpSensorSignal",            "Volt",    "Live",    "R"),
    ("AV",   5,       "AV_AOSignalValue",             "Volt",    "Live",    "R"),
    ("AV",   6,       "cfgDpSensorSignalMin",         "Volt",    "Config",  "R/W"),
    ("AV",   7,       "cfgDpSensorSignalMax",         "Volt",    "Config",  "R/W"),
    ("AV",   8,       "cfgDpSensorValueMin",          "in.wc.",  "Config",  "R/W"),
    ("AV",   9,       "cfgDpSensorValueMax",          "in.wc.",  "Config",  "R/W"),
    ("AV",   10,      "cfgDpWarningRangeHigh",        "in.wc.",  "Config",  "R/W"),
    ("AV",   11,      "cfgDpWarningRangeLow",         "in.wc.",  "Config",  "R/W"),
    ("AV",   12,      "cfgDpAlarmRangeHigh",          "in.wc.",  "Config",  "R/W"),
    ("AV",   13,      "cfgDpAlarmRangeLow",           "in.wc.",  "Config",  "R/W"),
    ("AV",   14,      "cfgWarningAnnunciatorVolume",  "%",       "Config",  "R/W"),
    ("AV",   15,      "cfgAlarmAnnunciatorVolume",    "%",       "Config",  "R/W"),
    ("AV",   16,      "cfgAlarmDelayTm(sec)",         "Second",  "Config",  "R/W"),
    ("AV",   17,      "cfgWarningDelayTm(sec)",       "Second",  "Config",  "R/W"),
    ("AV",   18,      "cfgMuteResetTm(sec)",          "Second",  "Config",  "R/W"),
    ("AV",   19,      "cfgDpAOSignalMin",             "Volt",    "Config",  "R/W"),
    ("AV",   20,      "cfgDpAOSignalMax",             "Volt",    "Config",  "R/W"),
    ("AV",   21,      "cfgDrSnrDelayTm(sec)",         "Second",  "Config",  "R/W"),
    ("AV",   22,      "cfgDpSnrSignalHysteresis",     "in.wc.",  "Config",  "R/W"),
    ("BV",   1,       "BV_DoorSwitchStatus",          "",        "Live",    "R"),
    ("BV",   2,       "cfgMuteEnable",                "",        "Config",  "R/W"),
    ("BV",   3,       "cfgWarningHighEnable",         "",        "Config",  "R/W"),
    ("BV",   4,       "cfgWarningLowEnable",          "",        "Config",  "R/W"),
    ("BV",   5,       "cfgAlarmHighEnable",           "",        "Config",  "R/W"),
    ("BV",   6,       "cfgAlarmLowEnable",            "",        "Config",  "R/W"),
    ("BV",   7,       "cfgDrSnrEnable",               "",        "Config",  "R/W"),
    ("BV",   8,       "cfgDrSnrNormOpen",             "",        "Config",  "R/W"),
    ("BV",   9,       "cfgDpAOEnable",                "",        "Config",  "R/W"),
    ("BV",   10,      "cfgDryContactNormOpen",        "",        "Config",  "R/W"),
    ("BV",   11,      "cfgDpSnrRangeCheckEnable",     "",        "Config",  "R/W"),
    ("BV",   12,      "BV_DO",                        "",        "Live",    "R"),
    ("BV",   13,      "BV_DpSenorOutOfRange",         "",        "Live",    "R"),
    ("BV",   14,      "BV_StandbyCmd",                "",        "Command", "R/W"),
    ("BV",   15,      "BV_AudibleInhibit",            "",        "Live",    "R"),
    ("File", 65536,   "Firmware",                     "",        "",        ""),
    ("File", 131072,  "Application",                  "",        "",        ""),
    ("File", 196609,  "Registration",                 "",        "Not Used","Not Used"),
    ("File", 262147,  "PointConfig",                  "",        "Not Used","Not Used"),
    ("MSV",  1,       "MSV_PressureStatus",           "",        "Live",    "R"),
    ("MSV",  2,       "cfgDpSensorSignalType",        "",        "Config",  "R/W"),
    ("MSV",  3,       "cfgDpAOSignalType",            "",        "Config",  "R/W"),
    ("MSV",  4,       "cfgDOAssignmentType",          "",        "Config",  "R/W"),
    ("MSV",  5,       "MSV_DpSensorSignalUnit",       "",        "Config",  "R"),
]

# PBC — (Type, ID, Name, Category, Unit, Access)
_PBC_ROWS: list[tuple] = [
    ("AI",  "1",   "LabTotalExhRet",           "Lab Zone",    "CFM",                                   "R"),
    ("AI",  "2",   "LabTotalSupply",            "Lab Zone",    "CFM",                                   "R"),
    ("AI",  "3",   "LabTotalGexFlow",           "Lab Zone",    "CFM",                                   "R"),
    ("AI",  "4",   "LabTotalMavFlow",           "Lab Zone",    "CFM",                                   "R"),
    ("AI",  "5",   "LabTotalHoodFlow",          "Lab Zone",    "CFM",                                   "R"),
    ("AI",  "6",   "LabTotalReturnFlow",        "Lab Zone",    "CFM",                                   "R"),
    ("AI",  "7",   "LabTotalBypassFlow",        "Lab Zone",    "CFM",                                   "R"),
    ("AI",  "8",   "LabZoneFlowOffset",         "Lab Zone",    "CFM",                                   "R"),
    ("AI",  "9",   "LabZoneEffFlowOffsetSP",    "Lab Zone",    "CFM",                                   "R"),
    ("AI",  "10",  "ACH",                       "Generic Zone","",                                      "R"),
    ("AI",  "30",  "LoSEATotalExhaust",         "LoSEA Zone",  "CFM",                                   "R"),
    ("AI",  "31",  "LoSEATotalReturn",          "LoSEA Zone",  "CFM",                                   "R"),
    ("AI",  "32",  "LoSEAZoneFlowOffset",       "LoSEA Zone",  "CFM",                                   "R"),
    ("AI",  "33",  "LoSEATotalSupply",          "LoSEA Zone",  "CFM",                                   "R"),
    ("AI",  "34",  "LoSEATotalExhRet",          "LoSEA Zone",  "CFM",                                   "R"),
    ("AI",  "35",  "LoSEAEffOffsetSP",          "LoSEA Zone",  "CFM",                                   "R"),
    ("AI",  "50",  "ValveEffFlowCmd1",          "LoSEA Valve", "CFM",                                   "R"),
    ("AI",  "51",  "Valveflow1",                "LoSEA Valve", "CFM",                                   "R"),
    ("AI",  "52",  "ValveVpot1",                "LoSEA Valve", "V",                                     "R"),
    ("AI",  "53",  "ValveEffFlowCmd2",          "LoSEA Valve", "CFM",                                   "R"),
    ("AI",  "54",  "Valveflow2",                "LoSEA Valve", "CFM",                                   "R"),
    ("AI",  "55",  "ValveVpot2",                "LoSEA Valve", "V",                                     "R"),
    ("AI",  "56",  "ValveEffFlowCmd3",          "LoSEA Valve", "CFM",                                   "R"),
    ("AI",  "57",  "Valveflow3",                "LoSEA Valve", "CFM",                                   "R"),
    ("AI",  "58",  "ValveVpot3",                "LoSEA Valve", "V",                                     "R"),
    ("AI",  "59",  "ValveEffFlowCmd4",          "LoSEA Valve", "CFM",                                   "R"),
    ("AI",  "60",  "Valveflow4",                "LoSEA Valve", "CFM",                                   "R"),
    ("AI",  "61",  "ValveVpot4",                "LoSEA Valve", "V",                                     "R"),
    ("AI",  "62",  "ValveAlarmStatusBits1",     "LoSEA Valve", "32-bit integer",                        "R"),
    ("AI",  "63",  "ValveAlarmStatusBits2",     "LoSEA Valve", "32-bit integer",                        "R"),
    ("AI",  "64",  "ValveAlarmStatusBits3",     "LoSEA Valve", "32-bit integer",                        "R"),
    ("AI",  "65",  "ValveAlarmStatusBits4",     "LoSEA Valve", "32-bit integer",                        "R"),
    ("AI",  "101", "UIO1ScaledValue",           "IO",          "Configured",                            "R"),
    ("AI",  "102", "UIO1RawValue",              "IO",          "Based on UIO characteristic",           "R"),
    ("AI",  "131", "UIO16ScaledValue",          "IO",          "Configured",                            "R"),
    ("AI",  "132", "UIO16RawValue",             "IO",          "Based on UIO characteristic",           "R"),
    ("AI",  "200", "Space_Temp",               "Generic DDC", "DegF",                                   "R"),
    ("AI",  "201", "EffCoolTempSP",             "Generic DDC", "DegF",                                   "R"),
    ("AI",  "202", "EffHeatTempSP",             "Generic DDC", "DegF",                                   "R"),
    ("AI",  "203", "CoolingDemand",             "Generic DDC", "%",                                      "R"),
    ("AI",  "204", "HeatingDemand",             "Generic DDC", "%",                                      "R"),
    ("AI",  "220", "RoomHumidity",              "Generic DDC", "%",                                      "R"),
    ("AI",  "221", "HumidifyDemand",            "Generic DDC", "%",                                      "R"),
    ("AI",  "222", "DehHumidifyDemand",         "Generic DDC", "%",                                      "R"),
    ("AI",  "999", "aiEngineering",             "Engineering", "",                                       "R"),
    ("AO",  "1",   "LabZoneFlowOffsetCmd",      "",            "CFM",                                    "RW"),
    ("AO",  "2",   "LoSEAZoneFlowOffsetCmd",    "",            "CFM",                                    "RW"),
    ("AO",  "101", "UIO1SignalCmd1",            "",            "Configured",                             "RW"),
    ("AO",  "116", "UIO16SignalCmd16",          "",            "Configured",                             "RW"),
    ("AO",  "200", "OccCoolSetpoint",           "",            "DegF",                                   "RW"),
    ("AO",  "201", "OccHeatSetpoint",           "",            "DegF",                                   "RW"),
    ("AO",  "202", "UnoccCoolSetpoint",         "",            "DegF",                                   "RW"),
    ("AO",  "203", "UnoccHeatSetpoint",         "",            "DegF",                                   "RW"),
    ("AO",  "204", "StndbyCoolSetpoint",        "",            "DegF",                                   "RW"),
    ("AO",  "205", "StndbyHeatSetpoint",        "",            "DegF",                                   "RW"),
    ("AO",  "206", "T_Offset_LVR_range",        "",            "%",                                      "RW"),
    ("AO",  "207", "AuxTempSetpt",              "",            "DegF",                                   "RW"),
    ("AO",  "220", "HumiditySetpt",             "",            "%",                                      "RW"),
    ("AO",  "999", "aoEngineering",             "",            "",                                       "R"),
    ("AV",  "50",  "ValveFlowCmd1",             "",            "CFM",                                    "RW"),
    ("AV",  "51",  "ValveFlowCmd2",             "",            "CFM",                                    "RW"),
    ("AV",  "52",  "ValveFlowCmd3",             "",            "CFM",                                    "RW"),
    ("AV",  "53",  "ValveFlowCmd4",             "",            "CFM",                                    "RW"),
    ("AV",  "210", "MinVentOccSP",              "",            "CFM",                                    "RW"),
    ("AV",  "211", "MinVentStandbySP",          "",            "CFM",                                    "RW"),
    ("AV",  "212", "MinVentUnoccSP",            "",            "CFM",                                    "RW"),
    ("AV",  "213", "MinVentVacantSP",           "",            "CFM",                                    "RW"),
    ("AV",  "999", "avEngineering",             "AI",          "",                                       "R"),
    ("BI",  "50",  "ValveJamALarm1",            "",            "TRUE/FALSE",                             "R"),
    ("BI",  "51",  "ValveFlowAlarm1",           "",            "TRUE/FALSE",                             "R"),
    ("BI",  "52",  "ValveJamALarm2",            "",            "TRUE/FALSE",                             "R"),
    ("BI",  "53",  "ValveFlowAlarm2",           "",            "TRUE/FALSE",                             "R"),
    ("BI",  "54",  "ValveJamAlarm3",            "",            "TRUE/FALSE",                             "R"),
    ("BI",  "55",  "ValveFlowAlarm3",           "",            "TRUE/FALSE",                             "R"),
    ("BI",  "56",  "ValveJamALarm4",            "",            "TRUE/FALSE",                             "R"),
    ("BI",  "57",  "ValveFlowAlarm4",           "",            "TRUE/FALSE",                             "R"),
    ("BI",  "999", "biEngineering",             "",            "",                                       "R"),
    ("BO",  "999", "boEngineering",             "",            "",                                       "R"),
    ("BV",  "50",  "ValveFlowOvridEnable",      "",            "TRUE/FALSE",                             "RW"),
    ("BV",  "51",  "ValveVpotOvridEnable",      "",            "Not Enabled in MVO template. Reserved",  "RW"),
    ("BV",  "52",  "UIOSignalOvridEnable",      "",            "TRUE/FALSE",                             "RW"),
    ("BV",  "999", "bvEngineering",             "",            "",                                       "R"),
    ("MSO", "1",   "EModeCmd",                  "",            "",                                       "RW"),
    ("MSO", "2",   "OccupancyCmd",              "",            "",                                       "RW"),
    ("MSO", "999", "msoEngineering",            "",            "",                                       "R"),
    ("MSV", "1",   "EffEmMode",                 "",            "",                                       "R"),
    ("MSV", "2",   "EffOccMode",                "",            "",                                       "R"),
    ("MSV", "3",   "LabZoneCtrlState",          "",            "Come from ErrorCode slot of LabZone FB", "R"),
    ("MSV", "4",   "LoSEAZoneCtrlState",        "",            "Come from ErrorCode slot of LoSEAZone FB", "R"),
    ("MSV", "50",  "ValveState1",               "",            "Disable/Opening/closing/AppOverride",    "R"),
    ("MSV", "51",  "ValveState2",               "",            "Disable/Opening/closing/AppOverride",    "R"),
    ("MSV", "52",  "ValveState3",               "",            "Disable/Opening/closing/AppOverride",    "R"),
    ("MSV", "53",  "ValveState4",               "",            "Disable/Opening/closing/AppOverride",    "R"),
    ("MSV", "200", "TempCtrlMode",              "",            "",                                       "R"),
    ("MSV", "999", "msvEngineering",            "",            "",                                       "R"),
]

# Each entry: (headers, rows)
_POINTS_LIST_DATA: dict[str, tuple[list[str], list[tuple]]] = {
    "ACM Points List": (_POINTS_HEADERS, [
        ("BI",  1,   "FlowAlarm",              "Alarm/Normal", "Feedback", "R"),
        ("BI",  2,   "JamAlarm",               "Alarm/Normal", "Feedback", "R"),
        ("MSV", 1,   "FSMStatus",              "",             "Feedback", "R"),
        ("MSV", 2,   "EmergencyMode",          "",             "",         "R"),
        ("MSV", 3,   "ValvePositionStatus",    "",             "Feedback", "R"),
        ("MSV", 4,   "AcuatorStatus",          "",             "",         "R"),
        ("MSV", 5,   "CurveStatus",            "",             "",         "R"),
        ("AO",  20,  "FlowCmdOverride",        "CFM",          "",         "RW"),
        ("AO",  21,  "VpotCmdOverride",        "Volt",         "",         "RW"),
        ("AI",  20,  "FlowFdbk",               "CFM",          "",         "R"),
        ("AI",  21,  "Vpot",                   "Volt",         "",         "R"),
        ("AI",  22,  "EffFlowSetpoint",        "CFM",          "",         "R"),
        ("AI",  200, "UIO1_PresentValue_In",   "%",            "",         "R"),
        ("AO",  200, "UIO1_PresentValue_Out",  "%",            "",         "R"),
        ("AI",  201, "UIO2_PresentValue_In",   "%",            "",         "R"),
        ("AO",  201, "UIO2_PresentValue_Out",  "%",            "",         "R"),
        ("AI",  202, "UIO3_PresentValue_In",   "%",            "",         "R"),
    ]),
    "FHD500 Points List": (_POINTS_HEADERS, [
        ("MSV", 1,   "HoodState",                "",              "Live",   "R"),
        ("AI",  1,   "SashOpening",              "%",             "Live",   "R"),
        ("AI",  2,   "FaceVelocity",             "FPM",           "Live",   "R"),
        ("AI",  3,   "HoodCommand",              "CFM",           "Live",   "R"),
        ("AI",  4,   "FlowFdbk",                 "CFM",           "Live",   "R"),
        ("BI",  1,   "OccupancyDetected",        "",              "Live",   "R"),
        ("BI",  2,   "AlarmSashBroken",          "",              "Live",   "R"),
        ("BI",  3,   "AlarmSashHeight",          "",              "Live",   "R"),
        ("BI",  4,   "AlarmEmergencyExhaust",    "",              "Live",   "R"),
        ("BI",  5,   "AlarmEnergyWaste",         "",              "Live",   "R"),
        ("AO",  1,   "FlowCmdOverride",          "CFM",           "Config", "RW"),
        ("AO",  2,   "FVCmdOverride",            "FPM",           "Config", "RW"),
        ("BO",  1,   "RemoteEMExhaustOverride",  "mVolts/ohms",   "Config", "RW"),
        ("BO",  2,   "HibernationOverride",      "",              "Config", "RW"),
        ("AI",  200, "UIO1_PresentValue_In",     "%",             "",       ""),
        ("AO",  200, "UIO1_PresentValue_Out",    "%",             "",       ""),
        ("AI",  201, "UIO2_PresentValue_In",     "%",             "",       ""),
        ("AO",  201, "UIO2_PresentValue_Out",    "%",             "",       ""),
        ("AI",  202, "UI1_PresentValue_In",      "%",             "",       ""),
        ("AI",  203, "UI2_PresentValue_In",      "%",             "",       ""),
        ("BO",  200, "DO_PresentValue_Out",      "",              "",       ""),
    ]),
    "PBC Points List": (_PBC_POINTS_HEADERS, _PBC_ROWS),
    "RPI Points List": (_POINTS_HEADERS, _RPI_ROWS),
}

# Pass/Fail tree item colors (work on both light and dark backgrounds)
_PASS_COLOR = QColor(16, 185, 129)   # #10b981
_FAIL_COLOR = QColor(239, 68,  68)   # #ef4444


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


class _BgWidget(QWidget):
    """
    Container widget that floats a semi-transparent logo overlay on top of all
    child content. The overlay QLabel is transparent for mouse events so it
    never interferes with interaction.
    """
    _OPACITY   = 0.12   # 12 % — subtle but clearly visible
    _SIZE_FRAC = 0.52   # logo diameter = 52 % of the shorter widget dimension

    def __init__(self) -> None:
        super().__init__()
        for _name in ("green.png", "PTT_Transparent_green.png"):
            path = _resource_path(_name)
            if os.path.exists(path):
                self._src = QPixmap(path)
                break
        else:
            self._src = QPixmap()

        self._overlay = QLabel(self)
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._overlay.setStyleSheet("background: transparent;")
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition()

    def _reposition(self) -> None:
        if self._src.isNull() or self.width() == 0:
            return
        size = int(min(self.width(), self.height()) * self._SIZE_FRAC)
        scaled = self._src.scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Bake opacity into a new pixmap so it renders correctly over any background
        faded = QPixmap(scaled.size())
        faded.fill(Qt.GlobalColor.transparent)
        p = QPainter(faded)
        p.setOpacity(self._OPACITY)
        p.drawPixmap(0, 0, scaled)
        p.end()

        self._overlay.setPixmap(faded)
        self._overlay.resize(faded.size())
        self._overlay.move(
            (self.width()  - faded.width())  // 2,
            (self.height() - faded.height()) // 2,
        )
        self._overlay.raise_()   # always on top of siblings


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


class BatchCheckoutDialog(QDialog):
    """
    Create multiple checkout sheets at once by incrementing a trailing number
    in the valve tag.  E.g. base tag "MAV-1-100", count 20 →
    MAV-1-100 … MAV-1-119 (all sharing technician, description, date).
    """

    def __init__(self, job: Job, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._job = job
        self.setWindowTitle(f"Batch Add Checkouts  \u2014  {_job_label(job)}")
        self.setModal(True)
        self.resize(480, 260)

        self._valve_tag   = QLineEdit()
        self._valve_tag.setPlaceholderText("e.g. MAV-1-100")
        self._count = QSpinBox()
        self._count.setRange(2, 500)
        self._count.setValue(10)
        self._technician  = QLineEdit()
        self._description = QLineEdit()
        self._date = QDateEdit(QDate.currentDate())
        self._date.setCalendarPopup(True)
        self._date.setDisplayFormat("yyyy-MM-dd")

        self._preview = QLabel("")
        self._preview.setObjectName("TagPreview")
        self._preview.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Starting Tag *", self._valve_tag)
        form.addRow("Count *",        self._count)
        form.addRow("Technician",     self._technician)
        form.addRow("Description",    self._description)
        form.addRow("Date",           self._date)

        btns = QDialogButtonBox()
        btns.addButton(QDialogButtonBox.StandardButton.Ok)
        btns.addButton(QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self._preview)
        lay.addWidget(btns)

        self._valve_tag.textChanged.connect(self._update_preview)
        self._count.valueChanged.connect(self._update_preview)
        self._update_preview()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _split_tag(tag: str) -> tuple[str, int, int] | None:
        """
        Split tag into (prefix, start_number, zero_pad_width).
        Returns None if the tag has no trailing integer.
        E.g. "MAV-1-100" → ("MAV-1-", 100, 0)
             "FH-007"    → ("FH-", 7, 3)
        """
        m = re.match(r'^(.*?)(\d+)$', tag)
        if not m:
            return None
        prefix, digits = m.group(1), m.group(2)
        return prefix, int(digits), len(digits) if digits.startswith("0") else 0

    def _tags(self) -> list[str] | None:
        raw = self._valve_tag.text().strip()
        if not raw:
            return None
        result = self._split_tag(raw)
        if result is None:
            return None
        prefix, start, pad = result
        count = self._count.value()
        if pad:
            pad = max(pad, len(str(start + count - 1)))
        tags = []
        for i in range(count):
            n = start + i
            tags.append(f"{prefix}{str(n).zfill(pad) if pad else n}")
        return tags

    def _update_preview(self) -> None:
        tags = self._tags()
        if tags is None:
            self._preview.setText(
                "\u26a0  Tag must end with a number (e.g. MAV-1-100)"
            )
        else:
            self._preview.setText(
                f"\u2713  Will create {len(tags)} sheets:  "
                f"{tags[0]}  \u2192  {tags[-1]}"
            )

    # ── Validation & result ───────────────────────────────────────────────────

    def accept(self) -> None:
        if not self._valve_tag.text().strip():
            QMessageBox.warning(self, "Required", "Starting Tag is required.")
            return
        if self._tags() is None:
            QMessageBox.warning(self, "Invalid Tag",
                                "The tag must end with a number so it can be incremented.\n"
                                "Example: MAV-1-100")
            return
        super().accept()

    def get_records(self) -> list[ValveCheckout]:
        tags = self._tags() or []
        tech  = self._technician.text().strip()
        desc  = self._description.text().strip()
        date  = self._date.date().toString("yyyy-MM-dd")
        return [
            ValveCheckout(
                job_id=self._job.id,
                valve_tag=tag,
                project=self._job.job_name,
                ats_job_number=self._job.job_number,
                technician=tech,
                description=desc,
                date=date,
            )
            for tag in tags
        ]


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

        icon_path = _resource_path("PTT_Normal_green.ico")
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
        batch_act = QAction("Batch Add Checkouts\u2026", self)
        batch_act.setShortcut("Ctrl+B")
        batch_act.triggered.connect(self._on_batch_add)
        file_menu.addAction(batch_act)
        file_menu.addSeparator()
        export_act = QAction("Export Selected Checkout\u2026", self)
        export_act.setShortcut("Ctrl+E")
        export_act.triggered.connect(self._on_export_current)
        file_menu.addAction(export_act)
        export_job_act = QAction("Export All Checkouts in Job\u2026", self)
        export_job_act.triggered.connect(self._on_export_job)
        file_menu.addAction(export_job_act)
        file_menu.addSeparator()
        backup_act = QAction("Backup Data\u2026", self)
        backup_act.triggered.connect(self._backup_data)
        file_menu.addAction(backup_act)
        file_menu.addSeparator()
        exit_act = QAction("Exit", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        view_menu = mb.addMenu("View")
        self._dark_mode_action = QAction("Dark Mode", self)
        self._dark_mode_action.setCheckable(True)
        s = QSettings("ATS Inc", self.APP_NAME)
        self._dark_mode_action.setChecked(bool(s.value("darkMode", True, type=bool)))
        self._dark_mode_action.triggered.connect(self._toggle_dark_mode)
        view_menu.addAction(self._dark_mode_action)

        tools_menu = mb.addMenu("Tools")
        test_act = QAction("Create Test Data", self)
        test_act.triggered.connect(self._create_test_data)
        tools_menu.addAction(test_act)

        pl_menu = tools_menu.addMenu("Points Lists")
        for _title in _POINTS_LIST_DATA:
            act = QAction(_title, self)
            act.triggered.connect(
                lambda checked=False, t=_title: self._open_points_list(t)
            )
            pl_menu.addAction(act)

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
        lay.setSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        new_job_btn = PrimaryButton("+ New Job")
        new_job_btn.clicked.connect(self._on_new_job)
        self._new_checkout_btn = PrimaryButton("+ New Checkout")
        self._new_checkout_btn.clicked.connect(self._on_new_checkout)
        self._new_checkout_btn.setEnabled(False)
        btn_row.addWidget(new_job_btn)
        btn_row.addWidget(self._new_checkout_btn)
        lay.addLayout(btn_row)

        batch_btn_row = QHBoxLayout()
        batch_btn_row.setSpacing(8)
        self._batch_btn = SecondaryButton("+ Batch Add")
        self._batch_btn.clicked.connect(self._on_batch_add)
        self._batch_btn.setEnabled(False)
        batch_btn_row.addWidget(self._batch_btn)
        lay.addLayout(batch_btn_row)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search checkouts\u2026")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._apply_tree_filter)
        lay.addWidget(self._search_edit)

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
        widget = _BgWidget()
        outer_lay = QVBoxLayout(widget)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(8)

        # Page 0: welcome  |  Page 1: checkout editor
        # Page 2: archived job summary  |  Page 3: active job summary
        self._main_stack = QStackedWidget()
        self._main_stack.addWidget(self._build_welcome_panel())  # index 0

        content_widget = QWidget()
        content_lay = QVBoxLayout(content_widget)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(8)
        content_lay.addWidget(self._build_header_panel())
        content_lay.addWidget(self._build_tabs(), stretch=1)
        self._main_stack.addWidget(content_widget)               # index 1

        self._main_stack.addWidget(self._build_archived_panel()) # index 2
        self._main_stack.addWidget(self._build_job_panel())      # index 3

        outer_lay.addWidget(self._main_stack, stretch=1)

        self._update_banner = self._build_update_banner()
        self._update_banner.setVisible(False)
        outer_lay.addWidget(self._update_banner)
        return widget

    # ── Welcome / instructions panel ──────────────────────────────────────────

    @staticmethod
    def _build_welcome_panel() -> QWidget:
        outer = QWidget()
        lay = QVBoxLayout(outer)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setContentsMargins(80, 40, 80, 40)
        lay.setSpacing(0)

        title = QLabel("Phoenix Valve Checkout Tool")
        title.setObjectName("ProjectTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        lay.addSpacing(6)

        sub = QLabel("Get started by creating a job, then add checkout sheets to it.")
        sub.setObjectName("ProjectSubtitle")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        lay.addWidget(sub)

        lay.addSpacing(32)

        steps = [
            ("1", "Create a Job",
             "Click  + New Job  in the sidebar, or press  Ctrl+J.\n"
             "A job groups all checkout sheets for one project or site."),
            ("2", "Add a Checkout Sheet",
             "Select a job, then click  + New Checkout  or press  Ctrl+N.\n"
             "Each sheet tracks wiring, configuration, and verification for one valve."),
            ("3", "Batch Add Checkout Sheets",
             "Click  + Batch Add  or press  Ctrl+B.\n"
             "Enter a starting tag (e.g. MAV-1-100) and a count to generate\n"
             "multiple sheets at once with automatically incremented valve tags."),
        ]

        for num, step_title, step_desc in steps:
            card = QWidget()
            card.setObjectName("Panel")
            card_lay = QHBoxLayout(card)
            card_lay.setContentsMargins(16, 16, 16, 16)
            card_lay.setSpacing(16)

            badge = QLabel(num)
            badge.setFixedSize(38, 38)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setObjectName("StepBadge")
            card_lay.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)

            text_col = QVBoxLayout()
            text_col.setSpacing(4)
            h_lbl = QLabel(step_title)
            h_lbl.setObjectName("SectionTitle")
            d_lbl = QLabel(step_desc)
            d_lbl.setWordWrap(True)
            text_col.addWidget(h_lbl)
            text_col.addWidget(d_lbl)
            card_lay.addLayout(text_col)

            lay.addWidget(card)
            lay.addSpacing(12)

        lay.addStretch()
        return outer

    # ── Archived job summary panel ────────────────────────────────────────────

    def _build_archived_panel(self) -> QWidget:
        """Container for the archived-job read-only summary view (page 2)."""
        outer = QWidget()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(8)

        # Header bar (same style as the regular header panel)
        hdr = QWidget()
        hdr.setObjectName("Panel")
        hdr.setFixedHeight(72)
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 12, 16, 12)
        hdr_lay.setSpacing(16)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._arch_hdr_title = QLabel("")
        self._arch_hdr_title.setObjectName("ProjectTitle")
        self._arch_hdr_sub = QLabel("")
        self._arch_hdr_sub.setObjectName("ProjectSubtitle")
        text_col.addWidget(self._arch_hdr_title)
        text_col.addWidget(self._arch_hdr_sub)
        hdr_lay.addLayout(text_col)
        hdr_lay.addStretch()

        arch_badge = QLabel("ARCHIVED")
        arch_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arch_badge.setFixedHeight(32)
        arch_badge.setObjectName("ArchivedBadge")
        hdr_lay.addWidget(arch_badge)

        restore_btn = QPushButton("Restore Job")
        restore_btn.setObjectName("RestoreBtn")
        restore_btn.clicked.connect(self._on_restore_archived_from_panel)
        hdr_lay.addWidget(restore_btn)

        outer_lay.addWidget(hdr)

        # Scrollable checkout list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._arch_list_widget = QWidget()
        self._arch_list_layout = QVBoxLayout(self._arch_list_widget)
        self._arch_list_layout.setContentsMargins(0, 0, 8, 0)
        self._arch_list_layout.setSpacing(4)
        self._arch_list_layout.addStretch()

        scroll.setWidget(self._arch_list_widget)
        outer_lay.addWidget(scroll, stretch=1)
        return outer

    @staticmethod
    def _build_checkouts_panel(records: list, show_type: bool = False) -> QWidget:
        panel = QWidget()
        panel.setObjectName("Panel")
        panel_lay = QVBoxLayout(panel)
        panel_lay.setContentsMargins(16, 12, 16, 12)
        panel_lay.setSpacing(0)

        title_lbl = QLabel("Checkout Sheets")
        title_lbl.setObjectName("SectionTitle")
        panel_lay.addWidget(title_lbl)
        panel_lay.addSpacing(10)

        for record in records:
            row = QWidget()
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(8, 8, 8, 8)
            row_lay.setSpacing(12)

            tag_lbl = QLabel(record.valve_tag or "(No Tag)")
            tag_lbl.setObjectName("CheckoutTag")
            tag_lbl.setMinimumWidth(100)
            if record.pass_fail == "Pass":
                tag_lbl.setStyleSheet(f"color: {_PASS_COLOR.name()};")
            elif record.pass_fail == "Fail":
                tag_lbl.setStyleSheet(f"color: {_FAIL_COLOR.name()};")
            row_lay.addWidget(tag_lbl)

            note_preview = (record.notes or "").split("\n")[0][:80]
            notes_lbl = QLabel(note_preview)
            notes_lbl.setObjectName("ProjectSubtitle")
            notes_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            row_lay.addWidget(notes_lbl, stretch=1)

            if show_type:
                type_lbl = QLabel(record.valve_type or "")
                type_lbl.setObjectName("ProjectSubtitle")
                type_lbl.setFixedWidth(150)
                type_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                row_lay.addWidget(type_lbl)

            if record.pass_fail in ("Pass", "Fail"):
                pf_lbl = QLabel(record.pass_fail.upper())
                pf_lbl.setFixedWidth(48)
                pf_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                pf_lbl.setObjectName("PassBadge" if record.pass_fail == "Pass" else "FailBadge")
                row_lay.addWidget(pf_lbl)
            else:
                spacer = QWidget()
                spacer.setFixedWidth(48)
                row_lay.addWidget(spacer)

            if record.technician:
                tech_lbl = QLabel(record.technician)
                tech_lbl.setObjectName("ProjectSubtitle")
                tech_lbl.setFixedWidth(120)
                row_lay.addWidget(tech_lbl)

            if record.date:
                date_lbl = QLabel(record.date)
                date_lbl.setObjectName("ProjectSubtitle")
                date_lbl.setFixedWidth(90)
                date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                row_lay.addWidget(date_lbl)

            panel_lay.addWidget(row)

            if record is not records[-1]:
                sep = QWidget()
                sep.setFixedHeight(1)
                sep.setObjectName("RowSep")
                panel_lay.addWidget(sep)

        return panel

    def _populate_archived_panel(self, job_id: str) -> None:
        """Fill the archived job summary panel for the given job."""
        job = self._store.get_job(job_id)
        if not job:
            return

        self._arch_current_job_id = job_id
        self._arch_hdr_title.setText(_job_label(job))

        records = self._store.records_for_job(job_id)
        total  = len(records)
        passes = sum(1 for r in records if r.pass_fail == "Pass")
        fails  = sum(1 for r in records if r.pass_fail == "Fail")
        self._arch_hdr_sub.setText(
            f"{total} checkout{'s' if total != 1 else ''}   \u2022   "
            f"{passes} passed   \u2022   {fails} failed"
        )

        # Clear old rows (keep the trailing stretch)
        while self._arch_list_layout.count() > 1:
            item = self._arch_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not records:
            empty_lbl = QLabel("No checkout sheets in this job.")
            empty_lbl.setObjectName("ProjectSubtitle")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._arch_list_layout.insertWidget(0, empty_lbl)
            return

        self._arch_list_layout.insertWidget(0, self._build_checkouts_panel(records, show_type=False))

    def _on_restore_archived_from_panel(self) -> None:
        job_id = getattr(self, "_arch_current_job_id", None)
        if job_id:
            self._restore_job(job_id)

    # ── Active job summary panel (page 3) ─────────────────────────────────────

    def _build_job_panel(self) -> QWidget:
        """Summary view shown when an active job is selected."""
        outer = QWidget()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(8)

        hdr = QWidget()
        hdr.setObjectName("Panel")
        hdr.setFixedHeight(88)
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 12, 16, 12)
        hdr_lay.setSpacing(16)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self._job_hdr_title = QLabel("")
        self._job_hdr_title.setObjectName("ProjectTitle")
        self._job_hdr_sub = QLabel("")
        self._job_hdr_sub.setObjectName("ProjectSubtitle")
        self._job_progress = QProgressBar()
        self._job_progress.setRange(0, 100)
        self._job_progress.setTextVisible(True)
        self._job_progress.setFixedHeight(14)
        text_col.addWidget(self._job_hdr_title)
        text_col.addWidget(self._job_hdr_sub)
        text_col.addWidget(self._job_progress)
        hdr_lay.addLayout(text_col)
        hdr_lay.addStretch()

        export_btn = SecondaryButton("Export All\u2026")
        export_btn.clicked.connect(self._on_export_job)
        hdr_lay.addWidget(export_btn)

        outer_lay.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._job_list_widget = QWidget()
        self._job_list_layout = QVBoxLayout(self._job_list_widget)
        self._job_list_layout.setContentsMargins(0, 0, 8, 0)
        self._job_list_layout.setSpacing(4)
        self._job_list_layout.addStretch()

        scroll.setWidget(self._job_list_widget)
        outer_lay.addWidget(scroll, stretch=1)
        return outer

    def _populate_job_panel(self, job_id: str) -> None:
        """Fill the active job summary panel for the given job."""
        job = self._store.get_job(job_id)
        if not job:
            return

        self._job_hdr_title.setText(_job_label(job))

        records = self._store.records_for_job(job_id)
        total    = len(records)
        passes   = sum(1 for r in records if r.pass_fail == "Pass")
        fails    = sum(1 for r in records if r.pass_fail == "Fail")
        reviewed = passes + fails
        self._job_hdr_sub.setText(
            f"{total} checkout{'s' if total != 1 else ''}   \u2022   "
            f"{passes} passed   \u2022   {fails} failed"
        )
        pct = int(reviewed / total * 100) if total else 0
        self._job_progress.setValue(pct)
        self._job_progress.setFormat(f"{reviewed}/{total} reviewed  ({pct}%)")

        # Clear previous rows (keep the trailing stretch)
        while self._job_list_layout.count() > 1:
            item = self._job_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not records:
            empty_lbl = QLabel("No checkout sheets in this job yet.")
            empty_lbl.setObjectName("ProjectSubtitle")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._job_list_layout.insertWidget(0, empty_lbl)
            return

        self._job_list_layout.insertWidget(0, self._build_checkouts_panel(records, show_type=True))

    # ── Header panel ─────────────────────────────────────────────────────────

    def _build_header_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("Panel")
        panel.setFixedHeight(72)
        lay = QHBoxLayout(panel)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(16)

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
        self._general_form = QFormLayout(panel)
        form = self._general_form
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

        self._f_valve_type = QComboBox()
        self._f_valve_type.addItems([
            "Fume Hood", "GEX", "MAV", "Snorkel",
            "Canopy", "Draw Down Bench", "Gas Cabinet",
            "CSCP Fume Hood", "PBC Room",
        ])
        self._f_valve_type.currentIndexChanged.connect(self._on_any_change)
        self._f_valve_type.currentTextChanged.connect(self._update_fume_hood_widgets)

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
        _cfm_validator = QIntValidator(0, 99999, self)
        self._f_emer_min.setValidator(_cfm_validator)
        self._f_valve_min_sp.setValidator(_cfm_validator)
        self._f_valve_max_sp.setValidator(_cfm_validator)

        self._tag_label = QLabel("Valve Tag #")
        form.addRow(self._tag_label,        self._f_valve_tag)
        form.addRow("Project",              self._f_project)
        form.addRow("ATS Job Number",  self._f_job_number)
        form.addRow("Technician",      self._f_technician)
        form.addRow("Description",     self._f_description)
        form.addRow("Model",           self._f_model)
        form.addRow("Valve Type",      self._f_valve_type)
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
        self._wiring_stack = QStackedWidget()

        # Page 0: Celeris (Phoenix + Black Box)
        celeris_spl = QSplitter(Qt.Orientation.Horizontal)
        self._phoenix_panel, self._phoenix_cbs, self._phoenix_table, self._celeris_sash_cb = \
            self._build_wiring_panel("PHOENIX AIR VALVE  \u2014  Wiring", PHOENIX_WIRING, sash_sensor=True)
        self._bb_panel, self._bb_cbs, _, _ = \
            self._build_wiring_panel("BLACK BOX  \u2014  Wiring", BB_WIRING, sash_sensor=False)
        celeris_spl.addWidget(self._phoenix_panel)
        celeris_spl.addWidget(self._bb_panel)
        celeris_spl.setStretchFactor(0, 1)
        celeris_spl.setStretchFactor(1, 1)
        self._wiring_stack.addWidget(celeris_spl)

        # Page 1: CSCP (ACM + DHV Black Box)
        cscp_spl = QSplitter(Qt.Orientation.Horizontal)
        self._acm_panel, self._acm_cbs, _, _ = \
            self._build_wiring_panel("ACTUATOR CONTROL MODULE (ACM)  \u2014  Wiring", ACM_WIRING, sash_sensor=False)
        self._dhv_panel, self._dhv_cbs, _, self._cscp_sash_cb = \
            self._build_wiring_panel("DHV BLACK BOX  \u2014  Wiring", DHV_BB_WIRING, sash_sensor=True)
        cscp_spl.addWidget(self._acm_panel)
        cscp_spl.addWidget(self._dhv_panel)
        cscp_spl.setStretchFactor(0, 1)
        cscp_spl.setStretchFactor(1, 1)
        self._wiring_stack.addWidget(cscp_spl)

        # Page 2: PBC Room (Left TB1/DO/UIO + Right Power/Comm/UIO)
        pbc_spl = QSplitter(Qt.Orientation.Horizontal)
        self._pbc_l_panel, self._pbc_l_cbs, _, _ = \
            self._build_wiring_panel("CSCP PBC  \u2014  TB1 Inputs / DO Relay / DO SSR / UIO",
                                     PBC_WIRING_LEFT, sash_sensor=False)
        self._pbc_r_panel, self._pbc_r_cbs, _, _ = \
            self._build_wiring_panel("CSCP PBC  \u2014  Power / Comm / UIO",
                                     PBC_WIRING_RIGHT, sash_sensor=False)
        pbc_spl.addWidget(self._pbc_l_panel)
        pbc_spl.addWidget(self._pbc_r_panel)
        pbc_spl.setStretchFactor(0, 1)
        pbc_spl.setStretchFactor(1, 1)
        self._wiring_stack.addWidget(pbc_spl)

        # Start with Celeris sash cb as default active reference
        self._sash_sensor_cb = self._celeris_sash_cb

        return self._wiring_stack

    def _build_wiring_panel(
        self,
        title: str,
        wiring_def: list[tuple],
        sash_sensor: bool,
    ) -> tuple[QScrollArea, dict, QTableWidget, Optional["QCheckBox"]]:
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

        _cbs = checkboxes   # capture for button closures

        def _bulk_set(checked: bool) -> None:
            self._loading = True
            for cb in _cbs.values():
                cb.setChecked(checked)
            self._loading = False
            self._on_any_change()

        check_all_btn = SecondaryButton("Check All")
        check_all_btn.setFixedHeight(36)
        check_all_btn.clicked.connect(lambda: _bulk_set(True))
        clear_all_btn = SecondaryButton("Clear All")
        clear_all_btn.setFixedHeight(36)
        clear_all_btn.clicked.connect(lambda: _bulk_set(False))

        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(8)
        hdr_row.addWidget(title_lbl)
        hdr_row.addStretch()
        hdr_row.addWidget(check_all_btn)
        hdr_row.addWidget(clear_all_btn)

        p_lay.addLayout(hdr_row)
        p_lay.addWidget(table, stretch=1)

        sash_cb = None
        if sash_sensor:
            sash_cb = QCheckBox("Sash Sensor Mounting complete")
            sash_cb.stateChanged.connect(self._on_any_change)
            p_lay.addWidget(sash_cb)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(panel_widget)
        return scroll, checkboxes, table, sash_cb

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
        cfg_lay.setSpacing(8)
        cfg_lbl = QLabel("Configuration")
        cfg_lbl.setObjectName("SectionTitle")
        cfg_lay.addWidget(cfg_lbl)

        self._cfg_table = _PhoenixTable(len(CONFIG_ROWS), 3)
        self._cfg_table.setHorizontalHeaderLabels(["Task", "CFM", "Height / Notes"])
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

        self._cfg_row_height = 42
        cfg_lay.addWidget(self._cfg_table)
        v.addWidget(cfg_panel)

        # Verification
        vfy_panel = QWidget()
        vfy_panel.setObjectName("Panel")
        vfy_lay = QVBoxLayout(vfy_panel)
        vfy_lay.setContentsMargins(12, 12, 12, 12)
        vfy_lay.setSpacing(8)
        vfy_lbl = QLabel("Verification")
        vfy_lbl.setObjectName("SectionTitle")
        vfy_lay.addWidget(vfy_lbl)

        self._vfy_table = _PhoenixTable(len(VERIFY_ROWS), 3)
        self._vfy_table.setHorizontalHeaderLabels(["Task", "Result", "Notes"])
        vh = self._vfy_table.horizontalHeader()
        vh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        vh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        vh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._vfy_table.setColumnWidth(1, 120)

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

        self._vfy_row_height = 42
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
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)
        lbl = QLabel("Notes")
        lbl.setObjectName("SectionTitle")
        lay.addWidget(lbl)
        self._notes_template_combo = QComboBox()
        for label, _ in _NOTES_TEMPLATES:
            self._notes_template_combo.addItem(label)
        self._notes_template_combo.currentIndexChanged.connect(self._on_notes_template_selected)
        lay.addWidget(self._notes_template_combo)
        self._notes_edit = QPlainTextEdit()
        self._notes_edit.textChanged.connect(self._on_any_change)
        lay.addWidget(self._notes_edit)
        return panel

    # ── Update banner ─────────────────────────────────────────────────────────

    def _build_update_banner(self) -> QWidget:
        banner = QWidget()
        banner.setObjectName("UpdateBanner")
        lay = QHBoxLayout(banner)
        lay.setContentsMargins(12, 8, 12, 8)
        self._update_msg = QLabel("")
        self._update_msg.setObjectName("UpdateMsg")
        lay.addWidget(self._update_msg)
        lay.addStretch()
        whats_new_btn = TertiaryButton("What's New?")
        whats_new_btn.clicked.connect(self._show_whats_new)
        lay.addWidget(whats_new_btn)
        install_btn = QPushButton("Install & Restart")
        install_btn.setObjectName("InstallBtn")
        install_btn.clicked.connect(self._install_update)
        lay.addWidget(install_btn)
        dismiss_btn = TertiaryButton("\u2715")
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

        # ── Archived jobs section ──────────────────────────────────────────────
        archived = self._store.archived_jobs()
        if archived:
            sep = QTreeWidgetItem(["── Archived Jobs ──"])
            sep.setFlags(Qt.ItemFlag.ItemIsEnabled)   # not selectable / draggable
            sep.setForeground(0, QBrush(QColor(130, 130, 130)))
            sep.setData(0, self._ROLE, ("separator", None))
            self._tree.addTopLevelItem(sep)

            arch_font = QFont()
            arch_font.setItalic(True)
            arch_font.setPointSize(10)
            gray = QBrush(QColor(140, 140, 140))

            for job in archived:
                arch_item = QTreeWidgetItem([_job_label(job)])
                arch_item.setFont(0, arch_font)
                arch_item.setForeground(0, gray)
                arch_item.setData(0, self._ROLE, ("archived_job", job.id))
                self._tree.addTopLevelItem(arch_item)

        self._tree.blockSignals(False)

        search = getattr(self, "_search_edit", None)
        if search:
            self._apply_tree_filter(search.text())

        if select_id:
            self._select_by_id(select_id)
        elif self._tree.topLevelItemCount() == 0:
            self._load_record(None)

    def _select_by_id(self, target_id: str) -> None:
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            role = item.data(0, self._ROLE)
            if role is None:
                continue
            kind, id_ = role
            if kind in ("job", "archived_job") and id_ == target_id:
                self._tree.setCurrentItem(item)
                return
            if kind == "job":
                for j in range(item.childCount()):
                    child = item.child(j)
                    _, cid = child.data(0, self._ROLE)
                    if cid == target_id:
                        self._tree.setCurrentItem(child)
                        return

    def _apply_tree_filter(self, text: str) -> None:
        q = text.strip().lower()
        for i in range(self._tree.topLevelItemCount()):
            job_item = self._tree.topLevelItem(i)
            role = job_item.data(0, self._ROLE)
            if role is None:
                continue
            kind, _ = role
            if kind in ("separator", "archived_job"):
                job_item.setHidden(bool(q))
                continue
            any_visible = False
            for j in range(job_item.childCount()):
                child = job_item.child(j)
                if q:
                    _, cid = child.data(0, self._ROLE)
                    rec = self._store.get(cid)
                    hidden = not (
                        q in child.text(0).lower()
                        or (rec and q in (rec.technician or "").lower())
                        or (rec and q in (rec.description or "").lower())
                        or (rec and q in (rec.valve_type or "").lower())
                    )
                else:
                    hidden = False
                child.setHidden(hidden)
                if not hidden:
                    any_visible = True
            if q:
                job_item.setHidden(not any_visible)
                if any_visible:
                    job_item.setExpanded(True)
            else:
                job_item.setHidden(False)

    @staticmethod
    def _apply_item_color(item: QTreeWidgetItem, pass_fail: str) -> None:
        if pass_fail == "Pass":
            item.setForeground(0, QBrush(_PASS_COLOR))
        elif pass_fail == "Fail":
            item.setForeground(0, QBrush(_FAIL_COLOR))
        else:
            item.setForeground(0, QBrush())  # reset to palette default

    def _selected_job_id(self) -> Optional[str]:
        """Return the job_id of the active (non-archived) job currently selected."""
        items = self._tree.selectedItems()
        if not items:
            return None
        kind, id_ = items[0].data(0, self._ROLE)
        if kind == "job":
            return id_
        if kind == "checkout":
            rec = self._store.get(id_)
            return rec.job_id if rec else None
        return None  # archived_job and separator are not usable as targets

    # ── Tree signals ──────────────────────────────────────────────────────────

    def _on_tree_changed(
        self,
        current: Optional[QTreeWidgetItem],
        _previous: Optional[QTreeWidgetItem],
    ) -> None:
        if current is None:
            self._main_stack.setCurrentIndex(0)   # welcome
            self._load_record(None)
            self._new_checkout_btn.setEnabled(False)
            self._batch_btn.setEnabled(False)
            return

        kind, id_ = current.data(0, self._ROLE)

        # Non-selectable separator — clear selection and go back to welcome
        if kind == "separator":
            self._tree.clearSelection()
            self._main_stack.setCurrentIndex(0)
            self._load_record(None)
            self._new_checkout_btn.setEnabled(False)
            self._batch_btn.setEnabled(False)
            return

        if kind == "archived_job":
            self._new_checkout_btn.setEnabled(False)
            self._batch_btn.setEnabled(False)
            self._populate_archived_panel(id_)
            self._main_stack.setCurrentIndex(2)   # archived summary
            return

        if kind == "job":
            self._new_checkout_btn.setEnabled(True)
            self._batch_btn.setEnabled(True)
            self._populate_job_panel(id_)
            self._main_stack.setCurrentIndex(3)   # active job summary
            return

        # kind == "checkout"
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._save_current()
        self._main_stack.setCurrentIndex(1)   # checkout editor
        self._new_checkout_btn.setEnabled(True)
        self._batch_btn.setEnabled(True)
        self._load_record(self._store.get(id_))

    def _on_tree_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if not item:
            return
        role = item.data(0, self._ROLE)
        if role is None:
            return
        kind, id_ = role
        if kind == "separator":
            return

        menu = QMenu(self)

        if kind == "job":
            add_act        = menu.addAction("Add Checkout to Job")
            batch_act      = menu.addAction("Batch Add Checkouts\u2026")
            menu.addSeparator()
            export_job_act = menu.addAction("Export All Checkouts to Excel\u2026")
            menu.addSeparator()
            archive_act    = menu.addAction("Archive Job")
            menu.addSeparator()
            del_act        = menu.addAction("Delete Job")
            action = menu.exec(self._tree.mapToGlobal(pos))
            if action == add_act:
                job = self._store.get_job(id_)
                if job:
                    self._open_new_checkout_for_job(job)
            elif action == batch_act:
                self._batch_add_for_job(id_)
            elif action == export_job_act:
                self._export_job(id_)
            elif action == archive_act:
                self._archive_job(id_)
            elif action == del_act:
                self._delete_job(id_)

        elif kind == "archived_job":
            restore_act = menu.addAction("Restore Job")
            menu.addSeparator()
            del_act     = menu.addAction("Delete Job Permanently")
            action = menu.exec(self._tree.mapToGlobal(pos))
            if action == restore_act:
                self._restore_job(id_)
            elif action == del_act:
                self._delete_job(id_)

        else:  # checkout
            export_act = menu.addAction("Export to Excel\u2026")
            menu.addSeparator()
            del_act = menu.addAction("Delete Checkout")
            action = menu.exec(self._tree.mapToGlobal(pos))
            if action == export_act:
                self._export_checkout(id_)
            elif action == del_act:
                self._delete_checkout(id_)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _create_test_data(self) -> None:
        """Create a test job with 5 varied valve checkouts for export testing."""
        if QMessageBox.question(
            self, "Create Test Data",
            "This will create a test job (TEST-001) with 7 sample checkout sheets.\n\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        job = Job(job_number="TEST-001", job_name="Export Test Project")
        self._store.add_job(job)

        # Shared helpers
        def pw(indices):  # build wiring dict — both Install and Wired checked
            w = {}
            for i in indices:
                w[f"p_{i}_i"] = True
                w[f"p_{i}_w"] = True
            return w

        def bw(indices):  # black-box wiring
            w = {}
            for i in indices:
                w[f"b_{i}_i"] = True
                w[f"b_{i}_w"] = True
            return w

        # ── Valve 1: Fume Hood — fully wired, Pass ─────────────────────────
        r1 = ValveCheckout(
            job_id=job.id,
            valve_tag="FH-L1-100",
            project="Export Test Project",
            ats_job_number="TEST-001",
            date="2026-04-16",
            technician="J. Glave",
            description="Lab 101 Fume Hood",
            model="CELERIS 2",
            valve_type="Fume Hood",
            pass_fail="Pass",
            emer_min="150",
            valve_min_sp="200",
            valve_max_sp="800",
            wiring={
                **pw([0,1,2,3,8,9,10,11,12,20,21,22,23,24]),
                **bw([0,1,2,3,4,5,6,7,8,9,10]),
            },
            sash_sensor_mounted=True,
            config={
                "valve_min_cfm": "200",   "valve_min_notes": "Verified at BAS",
                "valve_max_cfm": "800",   "valve_max_notes": "Verified at BAS",
                "sched_min_cfm": "175",   "sched_min_notes": "Scheduled setback",
                "sched_max_cfm": "750",   "sched_max_notes": "",
                "hood_sash_min_cfm": "180", "hood_sash_min_notes": "Sash @ 12\"",
                "hood_sash_max_cfm": "760", "hood_sash_max_notes": "Sash fully open",
            },
            verification={
                "face_velocity_result": "Pass",   "face_velocity_notes": "100 FPM @ 18\"",
                "sash_height_alarm_result": "Pass", "sash_height_alarm_notes": "Alarm @ 18\"",
                "sash_sensor_output_result": "Pass", "sash_sensor_output_notes": "0-10V confirmed",
                "low_flow_alarm_result": "Pass",  "low_flow_alarm_notes": "",
                "jam_alarm_result": "Pass",       "jam_alarm_notes": "",
                "emergency_exhaust_result": "Pass", "emergency_exhaust_notes": "EE to 800 CFM",
                "mute_function_result": "Pass",   "mute_function_notes": "10-min mute OK",
            },
            notes="All points verified. Sash sensor calibrated on site.\nLON comms confirmed with building controller.",
        )

        # ── Valve 2: GEX — partially wired, Fail ───────────────────────────
        r2 = ValveCheckout(
            job_id=job.id,
            valve_tag="GEX-2-200",
            project="Export Test Project",
            ats_job_number="TEST-001",
            date="2026-04-16",
            technician="J. Glave",
            description="Corridor GEX Valve",
            model="CELERIS 2",
            valve_type="GEX",
            pass_fail="Fail",
            emer_min="100",
            valve_min_sp="150",
            valve_max_sp="600",
            wiring=pw([0,1,8,9,20,21,22,23,24]),
            config={
                "valve_min_cfm": "150", "valve_min_notes": "",
                "valve_max_cfm": "600", "valve_max_notes": "Max not reached during test",
                "sched_min_cfm": "120", "sched_min_notes": "",
                "sched_max_cfm": "550", "sched_max_notes": "",
            },
            verification={
                "low_flow_alarm_result": "Fail", "low_flow_alarm_notes": "Alarm did not trigger — recheck wiring",
                "jam_alarm_result": "Pass",      "jam_alarm_notes": "",
            },
            notes="Low flow alarm failure. Contractor to recheck DO-0 wiring at controller.",
        )

        # ── Valve 3: MAV — fully wired, Pass ───────────────────────────────
        r3 = ValveCheckout(
            job_id=job.id,
            valve_tag="MAV-3-300",
            project="Export Test Project",
            ats_job_number="TEST-001",
            date="2026-04-16",
            technician="J. Glave",
            description="Lab 101 Supply Valve",
            model="CELERIS 2",
            valve_type="MAV",
            pass_fail="Pass",
            emer_min="",
            valve_min_sp="100",
            valve_max_sp="500",
            wiring=pw([2,3,4,5,8,9,10,11,12,20,21,22,23,24]),
            config={
                "valve_min_cfm": "100", "valve_min_notes": "Tracking fume hood",
                "valve_max_cfm": "500", "valve_max_notes": "",
                "sched_min_cfm": "80",  "sched_min_notes": "Night setback",
                "sched_max_cfm": "480", "sched_max_notes": "",
            },
            verification={
                "low_flow_alarm_result": "Pass", "low_flow_alarm_notes": "",
                "jam_alarm_result": "N/A",       "jam_alarm_notes": "Not applicable for MAV",
            },
            notes="Supply valve tracking confirmed against FH-L1-100.",
        )

        # ── Valve 4: Fume Hood — partial wiring, no pass/fail yet ──────────
        r4 = ValveCheckout(
            job_id=job.id,
            valve_tag="FH-L2-400",
            project="Export Test Project",
            ats_job_number="TEST-001",
            date="2026-04-16",
            technician="J. Glave",
            description="Lab 202 Fume Hood",
            model="CELERIS 2",
            valve_type="Fume Hood",
            pass_fail="",
            emer_min="150",
            valve_min_sp="200",
            valve_max_sp="800",
            wiring={
                **pw([0,1,20,21,22,23,24]),
                **bw([0,1,2]),
            },
            sash_sensor_mounted=False,
            config={
                "valve_min_cfm": "200", "valve_min_notes": "",
                "valve_max_cfm": "800", "valve_max_notes": "",
                "sched_min_cfm": "",    "sched_min_notes": "Pending BAS schedule",
                "sched_max_cfm": "",    "sched_max_notes": "",
                "hood_sash_min_cfm": "", "hood_sash_min_notes": "Sash sensor not yet mounted",
                "hood_sash_max_cfm": "", "hood_sash_max_notes": "",
            },
            verification={
                "face_velocity_result": "",      "face_velocity_notes": "Test incomplete",
                "sash_height_alarm_result": "N/A", "sash_height_alarm_notes": "",
                "sash_sensor_output_result": "", "sash_sensor_output_notes": "",
                "low_flow_alarm_result": "Pass", "low_flow_alarm_notes": "",
                "jam_alarm_result": "Pass",      "jam_alarm_notes": "",
                "emergency_exhaust_result": "",  "emergency_exhaust_notes": "Pending",
                "mute_function_result": "",      "mute_function_notes": "",
            },
            notes="Wiring partially complete. Sash sensor delivery delayed.\nRevisit scheduled for next week.",
        )

        # ── Valve 5: GEX — fully wired, Pass ───────────────────────────────
        r5 = ValveCheckout(
            job_id=job.id,
            valve_tag="GEX-5-500",
            project="Export Test Project",
            ats_job_number="TEST-001",
            date="2026-04-16",
            technician="J. Glave",
            description="Stockroom GEX Valve",
            model="CELERIS 2",
            valve_type="GEX",
            pass_fail="Pass",
            emer_min="80",
            valve_min_sp="120",
            valve_max_sp="450",
            wiring=pw([0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,20,21,22,23,24]),
            config={
                "valve_min_cfm": "120", "valve_min_notes": "Confirmed",
                "valve_max_cfm": "450", "valve_max_notes": "Confirmed",
                "sched_min_cfm": "100", "sched_min_notes": "",
                "sched_max_cfm": "420", "sched_max_notes": "",
            },
            verification={
                "low_flow_alarm_result": "Pass", "low_flow_alarm_notes": "Triggered at 100 CFM",
                "jam_alarm_result": "Pass",      "jam_alarm_notes": "Tested twice",
            },
            notes="All points verified. Clean install.",
        )

        def acm(indices):  # ACM wiring — both Install and Wired
            w = {}
            for i in indices:
                w[f"acm_{i}_i"] = True
                w[f"acm_{i}_w"] = True
            return w

        def dhv(indices):  # DHV BB wiring — both Install and Wired
            w = {}
            for i in indices:
                w[f"dhv_{i}_i"] = True
                w[f"dhv_{i}_w"] = True
            return w

        def pbc_l(indices):  # PBC left wiring
            w = {}
            for i in indices:
                w[f"pbc_l_{i}_i"] = True
                w[f"pbc_l_{i}_w"] = True
            return w

        def pbc_r(indices):  # PBC right wiring
            w = {}
            for i in indices:
                w[f"pbc_r_{i}_i"] = True
                w[f"pbc_r_{i}_w"] = True
            return w

        # ── Valve 6: CSCP Fume Hood — ACM, fully wired, Pass ──────────────
        r6 = ValveCheckout(
            job_id=job.id,
            valve_tag="ACM-L3-600",
            project="Export Test Project",
            ats_job_number="TEST-001",
            date="2026-04-16",
            technician="J. Glave",
            description="Lab 301 CSCP ACM Fume Hood",
            model="ACM (CSCP)",
            valve_type="CSCP Fume Hood",
            pass_fail="Pass",
            emer_min="120",
            valve_min_sp="180",
            valve_max_sp="700",
            wiring={
                **acm([0, 1, 2, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]),
                **dhv([0, 1, 2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21]),
            },
            sash_sensor_mounted=True,
            config={
                "valve_min_cfm": "180",   "valve_min_notes": "Confirmed at BAS",
                "valve_max_cfm": "700",   "valve_max_notes": "Confirmed at BAS",
                "sched_min_cfm": "160",   "sched_min_notes": "Night setback",
                "sched_max_cfm": "660",   "sched_max_notes": "",
                "hood_sash_min_cfm": "170", "hood_sash_min_notes": "Sash @ 10\"",
                "hood_sash_max_cfm": "690", "hood_sash_max_notes": "Sash @ 18\"",
            },
            verification={
                "face_velocity_result": "Pass",           "face_velocity_notes": "95 FPM @ 18\"",
                "sash_height_alarm_result": "Pass",        "sash_height_alarm_notes": "Triggered at 20\"",
                "sash_sensor_output_result": "Pass",       "sash_sensor_output_notes": "",
                "low_flow_alarm_result": "Pass",           "low_flow_alarm_notes": "",
                "jam_alarm_result": "Pass",                "jam_alarm_notes": "",
                "emergency_exhaust_result": "Pass",        "emergency_exhaust_notes": "Tested from BAS",
            },
            notes="CSCP ACM unit. T1L BACnet confirmed. Sash sensor calibrated.",
        )

        # ── Valve 7: PBC Room — partially wired, Fail ─────────────────────
        r7 = ValveCheckout(
            job_id=job.id,
            valve_tag="PBC-MDF-700",
            project="Export Test Project",
            ats_job_number="TEST-001",
            date="2026-04-16",
            technician="J. Glave",
            description="MDF Room PBC Controller",
            model="PBC (CSCP)",
            valve_type="PBC Room",
            pass_fail="Fail",
            wiring={
                **pbc_l([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 21, 22]),
                **pbc_r([3, 4, 5, 6, 7, 8, 9, 10, 13, 14, 15, 16, 17, 18]),
            },
            notes="BACnet MS/TP communication not established. Verify address 42 and baud rate. RS485 wiring confirmed.",
        )

        for r in (r1, r2, r3, r4, r5, r6, r7):
            self._store.add(r)

        self._refresh_tree(select_id=r1.id)
        QMessageBox.information(
            self, "Test Data Created",
            f"Created job '{job.job_number} — {job.job_name}' with 7 test valve checkouts.",
        )

    def _open_points_list(self, title: str) -> None:
        headers, rows = _POINTS_LIST_DATA.get(title, (_POINTS_HEADERS, []))

        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(760, 600)
        lay = QVBoxLayout(dlg)

        tbl = _PhoenixTable(len(rows), len(headers), dlg)
        tbl.setHorizontalHeaderLabels(headers)
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setStretchLastSection(True)

        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                tbl.setItem(r_idx, c_idx, QTableWidgetItem("" if val is None else str(val)))

        lay.addWidget(tbl)

        close_btn = SecondaryButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        dlg.exec()

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

    def _on_batch_add(self) -> None:
        job_id = self._selected_job_id()
        if not job_id:
            QMessageBox.information(self, "No Job Selected",
                                    "Select a job first, then batch add checkouts.")
            return
        self._batch_add_for_job(job_id)

    def _batch_add_for_job(self, job_id: str) -> None:
        job = self._store.get_job(job_id)
        if not job:
            return
        dlg = BatchCheckoutDialog(job, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        records = dlg.get_records()
        for record in records:
            self._store.add(record)
        self._refresh_tree(select_id=records[0].id)

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

    def _archive_job(self, job_id: str) -> None:
        job = self._store.get_job(job_id)
        if not job:
            return
        self._store.archive_job(job_id)
        if self._current_id:
            rec = self._store.get(self._current_id)
            if rec and rec.job_id == job_id:
                self._current_id = None
        self._refresh_tree()
        self._load_record(None)

    def _restore_job(self, job_id: str) -> None:
        self._store.restore_job(job_id)
        self._refresh_tree(select_id=job_id)

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
        issues = self._check_export_issues([record])
        if issues:
            msg = "Export warnings:\n\n" + "\n".join(issues) + "\n\nProceed anyway?"
            if QMessageBox.question(
                self, "Export Warnings", msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            ) != QMessageBox.StandardButton.Yes:
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
        issues = self._check_export_issues(records)
        if issues:
            msg = "Export warnings:\n\n" + "\n".join(issues) + "\n\nProceed anyway?"
            if QMessageBox.question(
                self, "Export Warnings", msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            ) != QMessageBox.StandardButton.Yes:
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
            summary_title = f"{job.job_number} \u2014 {job.job_name}" if job else ""
            export_records(records, path, summary_title=summary_title)
            QMessageBox.information(
                self, "Export Complete",
                f"Exported {len(records)} checkout{'s' if len(records) != 1 else ''} to:\n{path}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    @staticmethod
    def _check_export_issues(records: list) -> list[str]:
        issues = []
        for r in records:
            tag = r.valve_tag or "(No Tag)"
            if not (r.valve_tag or "").strip():
                issues.append(f"\u2022 {tag}: missing valve tag")
            if not r.pass_fail:
                issues.append(f"\u2022 {tag}: no Pass/Fail result set")
            if not (r.technician or "").strip():
                issues.append(f"\u2022 {tag}: no technician name")
            if r.notes and len(r.notes.split("\n")) > NOTES_MAX_LINES:
                issues.append(f"\u2022 {tag}: notes exceed {NOTES_MAX_LINES} lines (will be truncated in export)")
        return issues

    # ── Load / save record ────────────────────────────────────────────────────

    def _load_record(self, record: Optional[ValveCheckout]) -> None:
        self._loading = True
        self._current_id = record.id if record else None
        self._tabs.setEnabled(record is not None)

        if not record:
            # Switch to welcome page if tree has no current selection
            if self._tree.currentItem() is None:
                self._main_stack.setCurrentIndex(0)
            self._hdr_tag.setText("Select a job or checkout")
            self._hdr_sub.setText("")
            self._hdr_badge.setText("")
            self._hdr_badge.setObjectName("")
            self._hdr_badge.style().unpolish(self._hdr_badge)
            self._hdr_badge.style().polish(self._hdr_badge)
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
        self._f_valve_type.setCurrentText(record.valve_type or "Fume Hood")
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
        for cbs, prefix in self._wiring_boards():
            for (idx, fld), cb in cbs.items():
                cb.blockSignals(True)
                cb.setChecked(w.get(f"{prefix}_{idx}_{fld}", False))
                cb.blockSignals(False)
        for sash_cb in (self._celeris_sash_cb, self._cscp_sash_cb):
            sash_cb.blockSignals(True)
            sash_cb.setChecked(record.sash_sensor_mounted)
            sash_cb.blockSignals(False)

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
            self._hdr_badge.setObjectName("PassBadge")
        elif pf == "Fail":
            self._hdr_badge.setText("FAIL")
            self._hdr_badge.setObjectName("FailBadge")
        else:
            self._hdr_badge.setText("")
            self._hdr_badge.setObjectName("")
        self._hdr_badge.style().unpolish(self._hdr_badge)
        self._hdr_badge.style().polish(self._hdr_badge)

    # Keys of config/verify rows that are Fume Hood-only
    _FH_ONLY_CFG        = {"hood_sash_min", "hood_sash_max"}
    _FH_ONLY_VFY        = {"face_velocity", "sash_height_alarm", "sash_sensor_output", "emergency_exhaust"}
    _CELERIS_FH_ONLY_VFY = {"mute_function"}

    # General-tab form row indices for valve-specific SP fields
    _FORM_ROW_EMER_MIN   = 9
    _FORM_ROW_VALVE_MIN  = 10
    _FORM_ROW_VALVE_MAX  = 11

    # Tab indices
    _TAB_WIRING  = 1
    _TAB_CFG_VFY = 2

    def _update_fume_hood_widgets(self, valve_type: str) -> None:
        """Show/hide widgets based on valve type."""
        fume_hood = valve_type in ("Fume Hood", "CSCP Fume Hood")
        pbc_room  = valve_type == "PBC Room"

        # ── Tag label ──────────────────────────────────────────────────────────
        self._tag_label.setText("PBC Tag #" if pbc_room else "Valve Tag #")

        # ── General tab — valve SP fields ─────────────────────────────────────
        for row_idx in (self._FORM_ROW_EMER_MIN,
                        self._FORM_ROW_VALVE_MIN,
                        self._FORM_ROW_VALVE_MAX):
            self._general_form.setRowVisible(row_idx, not pbc_room)

        cscp_fh    = valve_type == "CSCP Fume Hood"
        celeris_fh = valve_type == "Fume Hood"

        # ── Tabs ──────────────────────────────────────────────────────────────
        self._tabs.setTabVisible(self._TAB_WIRING,  True)         # all types have wiring
        self._tabs.setTabVisible(self._TAB_CFG_VFY, not pbc_room)

        # ── Wiring stack page ─────────────────────────────────────────────────
        if cscp_fh:
            self._wiring_stack.setCurrentIndex(1)
            self._sash_sensor_cb = self._cscp_sash_cb
        elif pbc_room:
            self._wiring_stack.setCurrentIndex(2)
            self._sash_sensor_cb = self._celeris_sash_cb  # PBC has no sash sensor
        else:
            self._wiring_stack.setCurrentIndex(0)
            self._sash_sensor_cb = self._celeris_sash_cb

        # ── Celeris panel visibility (page 0 only) ────────────────────────────
        self._bb_panel.setVisible(celeris_fh)
        self._celeris_sash_cb.setVisible(celeris_fh)
        self._cscp_sash_cb.setVisible(cscp_fh)
        sash_text = "Sash Open Signal" if celeris_fh else ""
        for tbl_row in (1, 2):
            item = self._phoenix_table.item(tbl_row, 2)
            if item:
                item.setText(sash_text)

        # ── Config table — hide Fume Hood-only rows and resize ────────────────
        visible_cfg = 0
        for r_idx, (key, _) in enumerate(CONFIG_ROWS):
            hidden = (key in self._FH_ONLY_CFG) and not fume_hood
            self._cfg_table.setRowHidden(r_idx, hidden)
            if not hidden:
                visible_cfg += 1
        hdr_h = self._cfg_table.horizontalHeader().height()
        self._cfg_table.setFixedHeight(hdr_h + visible_cfg * self._cfg_row_height + 4)

        # ── Verification table — hide Fume Hood-only rows and resize ──────────
        visible_vfy = 0
        for r_idx, (key, _) in enumerate(VERIFY_ROWS):
            hidden = (
                (key in self._FH_ONLY_VFY and not fume_hood) or
                (key in self._CELERIS_FH_ONLY_VFY and not celeris_fh)
            )
            self._vfy_table.setRowHidden(r_idx, hidden)
            if not hidden:
                visible_vfy += 1
        hdr_h = self._vfy_table.horizontalHeader().height()
        self._vfy_table.setFixedHeight(hdr_h + visible_vfy * self._vfy_row_height + 4)

    def _wiring_boards(self) -> list[tuple[dict, str]]:
        return [
            (self._phoenix_cbs, "p"),
            (self._bb_cbs, "b"),
            (self._acm_cbs, "acm"),
            (self._dhv_cbs, "dhv"),
            (self._pbc_l_cbs, "pbc_l"),
            (self._pbc_r_cbs, "pbc_r"),
        ]

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
        record.valve_type     = self._f_valve_type.currentText()
        record.date           = self._f_date.date().toString("yyyy-MM-dd")
        record.pass_fail      = self._f_pass_fail.currentText()
        record.emer_min       = self._f_emer_min.text().strip()
        record.valve_min_sp   = self._f_valve_min_sp.text().strip()
        record.valve_max_sp   = self._f_valve_max_sp.text().strip()

        w: dict = {}
        for cbs, prefix in self._wiring_boards():
            for (idx, fld), cb in cbs.items():
                w[f"{prefix}_{idx}_{fld}"] = cb.isChecked()
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

    def _on_notes_template_selected(self, idx: int) -> None:
        if idx == 0:
            return
        _, snippet = _NOTES_TEMPLATES[idx]
        if snippet:
            current = self._notes_edit.toPlainText()
            sep = "\n" if current and not current.endswith("\n") else ""
            self._notes_edit.setPlainText(current + sep + snippet)
        self._notes_template_combo.blockSignals(True)
        self._notes_template_combo.setCurrentIndex(0)
        self._notes_template_combo.blockSignals(False)

    def _backup_data(self) -> None:
        from datetime import date as _date
        default_name = f"Phoenix_Checkout_Backup_{_date.today().isoformat()}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Backup Data", default_name,
            "JSON File (*.json)"
        )
        if not path:
            return
        try:
            shutil.copy2(DATA_FILE, path)
            QMessageBox.information(self, "Backup Complete", f"Data backed up to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Backup Failed", str(exc))

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
        QSettings("ATS Inc", self.APP_NAME).setValue("darkMode", dark)

    def _restore_settings(self) -> None:
        s = QSettings("ATS Inc", self.APP_NAME)
        dark_on = s.value("darkMode", True, type=bool)
        app: QApplication = QApplication.instance()  # type: ignore[assignment]
        if app:
            apply_dark_theme(app) if dark_on else apply_light_theme(app)
        geom = s.value("geometry")
        if geom:
            self.restoreGeometry(geom)

    def closeEvent(self, event) -> None:
        QSettings("ATS Inc", self.APP_NAME).setValue("geometry", self.saveGeometry())
        if hasattr(self, "_update_checker"):
            self._update_checker.wait(2000)
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
        QTreeView::branch:selected { background:#487cff; }
        QTreeView::branch:hover:!selected { background:#c3c6ce; }
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
        #RestoreBtn { background:#7c5c00; border:1px solid #f0b429; color:#f0b429; font-weight:700; }
        #RestoreBtn:hover { background:#a07800; }
    """)


_EMBEDDED_QSS = """
QMainWindow{background-color:#0a0e27;color:#ffffff;}
QWidget{color:#ffffff;font-family:"Segoe UI",Arial,sans-serif;font-size:11pt;}
QMenuBar{background-color:#0a0e27;color:#ffffff;border-bottom:1px solid #2d3748;padding:4px 0px;spacing:16px;}
QMenuBar::item:selected{background-color:#1f2937;color:#3b82f6;}
QMenuBar::item:pressed{background-color:#1e3a8a;}
QMenu{background-color:#141829;color:#ffffff;border:1px solid #2d3748;border-radius:4px;padding:4px 0px;}
QMenu::item{padding:8px 16px;}
QMenu::item:selected{background-color:#1f2937;color:#3b82f6;}
QMenu::item:pressed{background-color:#1e3a8a;}
QMenu::separator{background-color:#2d3748;height:1px;margin:4px 0px;}
QPushButton,QToolButton{background-color:#dc2626;color:#ffffff;border:none;border-radius:6px;padding:6px 14px;font-weight:600;font-size:11pt;font-family:"Segoe UI",sans-serif;}
QPushButton:hover,QToolButton:hover{background-color:#b91c1c;}
QPushButton:pressed,QToolButton:pressed{background-color:#991b1b;}
QPushButton:focus{outline:none;border:2px solid #3b82f6;}
QPushButton:disabled,QToolButton:disabled{background-color:#4b5563;color:#6b7280;}
QPushButton#secondaryButton{background-color:#1e3a8a;}
QPushButton#secondaryButton:hover{background-color:#1e40af;}
QPushButton#tertiaryButton{background-color:transparent;border:1px solid #4b5563;color:#3b82f6;}
QPushButton#tertiaryButton:hover{background-color:#1f2937;border:1px solid #3b82f6;}
QLineEdit{background-color:#141829;color:#ffffff;border:1px solid #2d3748;border-radius:6px;padding:6px 8px;selection-background-color:#3b82f6;}
QLineEdit:focus{border:2px solid #3b82f6;}
QLineEdit:disabled{background-color:#050810;color:#6b7280;}
QTextEdit,QPlainTextEdit{background-color:#141829;color:#ffffff;border:1px solid #2d3748;border-radius:6px;padding:6px 8px;selection-background-color:#3b82f6;}
QTextEdit:focus,QPlainTextEdit:focus{border:2px solid #3b82f6;}
QTextEdit:disabled,QPlainTextEdit:disabled{background-color:#050810;color:#6b7280;}
QComboBox{background-color:#141829;color:#ffffff;border:1px solid #2d3748;border-radius:6px;padding:6px 8px;}
QComboBox:focus{border:2px solid #3b82f6;}
QComboBox:disabled{background-color:#050810;color:#6b7280;}
QComboBox::drop-down{border:none;padding-right:8px;}
QComboBox::down-arrow{image:none;}
QComboBox QAbstractItemView{background-color:#141829;color:#ffffff;selection-background-color:#3b82f6;border:1px solid #2d3748;outline:none;}
QDateEdit{background-color:#141829;color:#ffffff;border:1px solid #2d3748;border-radius:6px;padding:6px 8px;}
QDateEdit:focus{border:2px solid #3b82f6;}
QSpinBox,QDoubleSpinBox{background-color:#141829;color:#ffffff;border:1px solid #2d3748;border-radius:6px;padding:6px 8px;}
QSpinBox:focus,QDoubleSpinBox:focus{border:2px solid #3b82f6;}
QSpinBox::up-button,QDoubleSpinBox::up-button,QSpinBox::down-button,QDoubleSpinBox::down-button{background-color:#050810;border:none;width:20px;}
QSpinBox::up-button:hover,QDoubleSpinBox::up-button:hover,QSpinBox::down-button:hover,QDoubleSpinBox::down-button:hover{background-color:#1f2937;}
QCheckBox{color:#ffffff;spacing:8px;}
QCheckBox::indicator{width:18px;height:18px;border-radius:4px;border:1px solid #4b5563;background-color:#141829;}
QCheckBox::indicator:hover{border:1px solid #3b82f6;background-color:#1f2937;}
QCheckBox::indicator:checked{background-color:#10b981;border:1px solid #10b981;}
QCheckBox::indicator:focus{border:2px solid #3b82f6;}
QRadioButton{color:#ffffff;spacing:8px;}
QRadioButton::indicator{width:18px;height:18px;border-radius:9px;border:1px solid #4b5563;background-color:#141829;}
QRadioButton::indicator:hover{border:1px solid #3b82f6;}
QRadioButton::indicator:checked{background-color:#1e3a8a;border:1px solid #1e3a8a;}
QLabel{color:#ffffff;font-family:"Segoe UI",sans-serif;}
QLabel#title{font-size:20pt;font-weight:bold;}
QLabel#sectionTitle{font-size:13pt;font-weight:600;}
QLabel#subtitle{font-size:11pt;color:#d1d5db;}
QLabel#hint{font-size:9pt;color:#9ca3af;}
QTabWidget::pane{border:1px solid #2d3748;background-color:#141829;}
QTabBar::tab{background-color:#050810;color:#9ca3af;padding:6px 18px;border:1px solid #2d3748;border-bottom:none;border-radius:6px 6px 0 0;font-weight:500;}
QTabBar::tab:selected{background-color:#141829;color:#ffffff;font-weight:600;border-bottom:3px solid #dc2626;}
QTabBar::tab:hover:!selected{background-color:#1f2937;color:#d1d5db;}
QTableWidget,QTableView{background-color:transparent;alternate-background-color:rgba(10,14,39,140);gridline-color:#2d3748;border:1px solid #2d3748;border-radius:6px;color:#ffffff;}
QTableWidget::item,QTableView::item{background-color:rgba(20,24,41,140);padding:3px 6px;border:none;color:#ffffff;}
QTableWidget::item:alternate,QTableView::item:alternate{background-color:rgba(10,14,39,140);}
QTableWidget::item:selected,QTableView::item:selected{background-color:#1e40af;color:#ffffff;}
QTableWidget::item:hover,QTableView::item:hover{background-color:#1f2937;}
QHeaderView::section{background-color:rgba(5,8,16,180);color:#e5e7eb;padding:6px 8px;border:none;border-right:1px solid #2d3748;border-bottom:1px solid #2d3748;font-weight:600;}
QHeaderView::section:hover{background-color:#1f2937;}
QTreeWidget{background:transparent;border:1px solid #2d3748;border-radius:10px;padding:4px;color:#ececec;outline:none;}
QTreeWidget::item{border-radius:6px;padding:5px 8px;margin:1px 0;}
QTreeWidget::item:selected{background:#1e3a8a;color:white;}
QTreeWidget::item:hover:!selected{background:#1f2937;}
QTreeView::branch{background:transparent;}
QTreeView::branch:selected{background:#1e3a8a;}
QTreeView::branch:hover:!selected{background:#1f2937;}
QScrollBar:vertical{background-color:#0a0e27;width:8px;border:none;}
QScrollBar::handle:vertical{background-color:#4b5563;border-radius:4px;min-height:20px;}
QScrollBar::handle:vertical:hover{background-color:#6b7280;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;border:none;background:none;}
QScrollBar:horizontal{background-color:#0a0e27;height:8px;border:none;}
QScrollBar::handle:horizontal{background-color:#4b5563;border-radius:4px;min-width:20px;}
QScrollBar::handle:horizontal:hover{background-color:#6b7280;}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0;border:none;background:none;}
QProgressBar{border:1px solid #2d3748;border-radius:6px;background-color:#050810;text-align:center;color:#ffffff;}
QProgressBar::chunk{background-color:#dc2626;border-radius:4px;}
QGroupBox{color:#ffffff;border:1px solid #2d3748;border-radius:8px;margin-top:12px;padding-top:12px;font-weight:600;}
QGroupBox::title{subcontrol-origin:margin;subcontrol-position:top left;padding:0px 4px;}
QDialog{background-color:#0a0e27;}
QMessageBox QLabel{color:#ffffff;}
QMessageBox QPushButton{min-width:80px;}
QSplitter::handle{background-color:#2d3748;}
QSplitter::handle:hover{background-color:#3b82f6;}
QFrame[frameShape="4"],QFrame[frameShape="5"]{border:1px solid #2d3748;background-color:transparent;}
QToolTip{background-color:#141829;color:#ffffff;border:1px solid #2d3748;padding:6px 10px;border-radius:4px;}
QStatusBar{background-color:#050810;color:#d1d5db;border-top:1px solid #2d3748;padding:2px 12px;}
QFormLayout QLabel{color:#9ca3af;}
#Panel,#StatCard{background:rgba(20,24,41,180);border:1px solid #2d3748;border-radius:14px;}
QLabel#ProjectTitle{font-size:14pt;font-weight:700;color:#ffffff;}
QLabel#ProjectSubtitle{color:#9ca3af;font-size:10pt;}
QLabel#SectionTitle{font-size:12pt;font-weight:600;color:#ffffff;}
#UpdateBanner{background:rgba(30,58,138,220);border-top:1px solid #3b82f6;}
QLabel#UpdateMsg{color:#93c5fd;font-weight:600;}
#InstallBtn{background:#dc2626;border:1px solid #ef4444;color:white;font-weight:700;}
#InstallBtn:hover{background:#b91c1c;}
#RestoreBtn{background:#92400e;border:1px solid #f59e0b;color:#f59e0b;font-weight:700;}
#RestoreBtn:hover{background:#b45309;}
QLabel#PassBadge{background:#10b981;color:white;border-radius:8px;font-weight:700;font-size:10pt;padding:2px 6px;}
QLabel#FailBadge{background:#ef4444;color:white;border-radius:8px;font-weight:700;font-size:10pt;padding:2px 6px;}
QLabel#ArchivedBadge{background:#92400e;color:#f59e0b;border-radius:8px;font-weight:700;font-size:10pt;padding:0px 10px;}
QLabel#StepBadge{background:#1e3a8a;color:white;border-radius:19px;font-weight:700;font-size:13pt;}
QLabel#TagPreview{color:#3b82f6;font-size:10pt;}
QWidget#RowSep{background:rgba(45,55,72,120);border:none;}
QLabel#CheckoutTag{font-size:11pt;font-weight:500;color:#ffffff;}
"""


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in [
        (QPalette.ColorRole.Window,          QColor(10, 14, 39)),
        (QPalette.ColorRole.WindowText,      QColor(255, 255, 255)),
        (QPalette.ColorRole.Base,            QColor(20, 24, 41)),
        (QPalette.ColorRole.AlternateBase,   QColor(15, 18, 25)),
        (QPalette.ColorRole.ToolTipBase,     QColor(20, 24, 41)),
        (QPalette.ColorRole.ToolTipText,     QColor(255, 255, 255)),
        (QPalette.ColorRole.Text,            QColor(255, 255, 255)),
        (QPalette.ColorRole.Button,          QColor(20, 24, 41)),
        (QPalette.ColorRole.ButtonText,      QColor(255, 255, 255)),
        (QPalette.ColorRole.BrightText,      QColor(220, 38, 38)),
        (QPalette.ColorRole.Highlight,       QColor(59, 130, 246)),
        (QPalette.ColorRole.HighlightedText, QColor(255, 255, 255)),
        (QPalette.ColorRole.Link,            QColor(59, 130, 246)),
    ]:
        palette.setColor(role, color)
    app.setPalette(palette)
    qss_path = _resource_path("phoenix_style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r") as fh:
            app.setStyleSheet(fh.read())
    else:
        # Embedded fallback — keeps full styling when auto-update only replaces the exe
        app.setStyleSheet(_EMBEDDED_QSS)


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
