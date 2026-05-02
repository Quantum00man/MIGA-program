from __future__ import annotations

import json
import sys
import traceback
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QProgressBar,
)

import rb87_bias_coils_current_scan as core


class SimulationWorker(QObject):
    finished = Signal(object)
    error = Signal(str)
    status = Signal(str)

    def __init__(self, config: core.SimulationConfig):
        super().__init__()
        self.config = config

    def run(self) -> None:
        try:
            output_dir = Path(core.__file__).resolve().parent / self.config.output.directory
            output_dir.mkdir(parents=True, exist_ok=True)

            self.status.emit("Running coarse current scan...")
            coarse_result = core.run_scan(self.config)

            self.status.emit("Refining around the coarse optimum...")
            refinement_result = core.refine_best_current(self.config, coarse_result)
            best_result = coarse_result["best_result"] if refinement_result is None else refinement_result["best_result"]

            self.status.emit("Saving figures and data products...")
            csv_path = core.save_scan_csv(coarse_result["records"], output_dir, self.config.output.prefix)
            refined_csv_path = None
            if refinement_result is not None and refinement_result["records"]:
                refined_csv_path = core.save_scan_csv(
                    refinement_result["records"],
                    output_dir,
                    f"{self.config.output.prefix}_refined",
                )
            overview_path = core.make_overview_figure(
                self.config,
                coarse_result,
                best_result,
                refinement_result,
                output_dir,
                self.config.output.prefix,
            )
            dynamics_path = core.make_dynamics_figure(
                self.config,
                best_result,
                output_dir,
                self.config.output.prefix,
            )
            summary_path = core.write_summary(
                self.config,
                coarse_result,
                best_result,
                refinement_result,
                output_dir,
                self.config.output.prefix,
            )
            resolved_config_path = core.save_resolved_config(
                self.config,
                output_dir,
                self.config.output.prefix,
            )

            bundle = {
                "config": self.config,
                "coarse_result": coarse_result,
                "refinement_result": refinement_result,
                "best_result": best_result,
                "paths": {
                    "output_dir": output_dir,
                    "csv": csv_path,
                    "refined_csv": refined_csv_path,
                    "overview": overview_path,
                    "dynamics": dynamics_path,
                    "summary": summary_path,
                    "resolved_config": resolved_config_path,
                },
            }
            self.finished.emit(bundle)
        except Exception:
            self.error.emit(traceback.format_exc())


class MetricCard(QFrame):
    def __init__(self, title: str, accent: str = "#1b5d73"):
        super().__init__()
        self.setObjectName("MetricCard")
        self.setStyleSheet(
            f"""
            QFrame#MetricCard {{
                background: white;
                border: 1px solid #d8d4cc;
                border-left: 4px solid {accent};
                border-radius: 14px;
            }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #6e756f; font-size: 11px; font-weight: 600; letter-spacing: 0.4px;")
        layout.addWidget(self.title_label)

        self.value_label = QLabel("--")
        self.value_label.setWordWrap(True)
        self.value_label.setStyleSheet("color: #13242d; font-size: 18px; font-weight: 700;")
        layout.addWidget(self.value_label)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet("color: #5b625d; font-size: 11px;")
        layout.addWidget(self.detail_label)

    def set_text(self, value: str, detail: str = "") -> None:
        self.value_label.setText(value)
        self.detail_label.setText(detail)


class ResizableImageLabel(QLabel):
    def __init__(self, placeholder_text: str):
        super().__init__(placeholder_text)
        self._original_pixmap = QPixmap()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(420)
        self.setWordWrap(True)

    def set_original_pixmap(self, pixmap: QPixmap) -> None:
        self._original_pixmap = pixmap
        self._refresh_pixmap()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self._original_pixmap.isNull():
            self.setPixmap(QPixmap())
            return
        scaled = self._original_pixmap.scaled(
            max(self.width() - 24, 200),
            max(self.height() - 24, 200),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.setPixmap(scaled)


class PlotPanel(QFrame):
    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.setObjectName("PlotPanel")
        self.setStyleSheet(
            """
            QFrame#PlotPanel {
                background: white;
                border: 1px solid #d8d4cc;
                border-radius: 16px;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(4)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #10242e; font-size: 18px; font-weight: 700;")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet("color: #5c665f; font-size: 12px;")
        header.addWidget(title_label)
        header.addWidget(subtitle_label)
        layout.addLayout(header)

        self.image_label = ResizableImageLabel("Run a simulation to populate this panel.")
        self.image_label.setStyleSheet(
            """
            QLabel {
                background: #f2efe8;
                border: 1px dashed #c8c4bc;
                border-radius: 12px;
                color: #6a706c;
                font-size: 13px;
            }
            """
        )
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.image_label, stretch=1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.open_button = QPushButton("Open Full-Size PNG")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_image)
        button_row.addWidget(self.open_button)
        layout.addLayout(button_row)

        self.image_path: Path | None = None

    def set_image(self, path: Path | None) -> None:
        self.image_path = path
        if path is None or not path.exists():
            self.image_label.setText("Image not available yet.")
            self.image_label.set_original_pixmap(QPixmap())
            self.open_button.setEnabled(False)
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.image_label.setText(f"Could not load image:\n{path}")
            self.image_label.set_original_pixmap(QPixmap())
            self.open_button.setEnabled(False)
            return

        self.image_label.set_original_pixmap(pixmap)
        self.image_label.setStyleSheet(
            """
            QLabel {
                background: #fbfaf7;
                border: 1px solid #ddd7cb;
                border-radius: 12px;
                padding: 8px;
            }
            """
        )
        self.open_button.setEnabled(True)

    def open_image(self) -> None:
        if self.image_path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.image_path)))


class BiasCoilsCurrentScanWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rb87 Bias-Coil Molasses Simulator")
        self.resize(1560, 980)
        self.last_bundle: dict | None = None
        self.worker_thread: QThread | None = None
        self.worker: SimulationWorker | None = None

        self._set_app_style()
        self._build_ui()
        self.apply_config(core.SimulationConfig())

    def _set_app_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f4f0e8;
            }
            QWidget {
                color: #16252d;
                font-size: 12px;
            }
            QGroupBox {
                background: white;
                border: 1px solid #d9d4ca;
                border-radius: 16px;
                margin-top: 12px;
                font-weight: 700;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #154e61;
                font-size: 13px;
            }
            QLabel[muted="true"] {
                color: #67716b;
            }
            QPushButton {
                background: #1b5d73;
                border: none;
                border-radius: 12px;
                color: white;
                font-weight: 700;
                padding: 10px 16px;
            }
            QPushButton:hover {
                background: #1f6b84;
            }
            QPushButton:disabled {
                background: #b6c2c7;
                color: #eef2f3;
            }
            QPushButton[secondary="true"] {
                background: #ebe7dd;
                color: #17313c;
                border: 1px solid #d6d0c5;
            }
            QPushButton[secondary="true"]:hover {
                background: #f1ece2;
            }
            QLineEdit, QDoubleSpinBox, QSpinBox {
                background: #fbfaf7;
                border: 1px solid #d8d3c9;
                border-radius: 10px;
                padding: 6px 8px;
                min-height: 30px;
            }
            QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus {
                border: 1px solid #1b5d73;
            }
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background: #ebe6dc;
                color: #48524c;
                border-radius: 10px;
                padding: 10px 16px;
                margin-right: 6px;
            }
            QTabBar::tab:selected {
                background: #1b5d73;
                color: white;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QTextBrowser {
                background: white;
                border: 1px solid #d8d4cc;
                border-radius: 14px;
                padding: 10px;
            }
            QProgressBar {
                background: #ebe7dd;
                border: 1px solid #d8d4cc;
                border-radius: 8px;
                text-align: center;
                color: #17313c;
            }
            QProgressBar::chunk {
                background: #1b5d73;
                border-radius: 8px;
            }
            """
        )

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        header = self._build_header()
        root_layout.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        root_layout.addWidget(splitter, stretch=1)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_container = QWidget()
        left_scroll.setWidget(left_container)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(6, 6, 10, 6)
        left_layout.setSpacing(14)
        splitter.addWidget(left_scroll)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(10, 6, 6, 6)
        right_layout.setSpacing(14)
        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([460, 1080])

        self._build_control_panels(left_layout)
        left_layout.addStretch(1)

        self._build_results_area(right_layout)
        self._build_status_bar()

    def _build_header(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("HeaderFrame")
        frame.setStyleSheet(
            """
            QFrame#HeaderFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #123f4d,
                    stop: 1 #365b49
                );
                border-radius: 20px;
            }
            """
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(6)

        title = QLabel("Rb87 Bias-Coil Optical Molasses Simulator")
        title_font = QFont("Georgia", 20)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: white;")
        layout.addWidget(title)

        subtitle = QLabel(
            "A current-domain control surface for three-axis compensation coils, with "
            "field conversion, coarse-to-refined scans, and publication-minded outputs."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: rgba(255, 255, 255, 0.88); font-size: 13px;")
        layout.addWidget(subtitle)

        return frame

    def _build_control_panels(self, parent_layout: QVBoxLayout) -> None:
        controls_bar = QGroupBox("Session Controls")
        bar_layout = QVBoxLayout(controls_bar)
        bar_layout.setSpacing(10)

        button_row = QHBoxLayout()
        self.run_button = QPushButton("Run Simulation")
        self.run_button.clicked.connect(self.run_simulation)
        button_row.addWidget(self.run_button)

        self.load_button = QPushButton("Load Config")
        self.load_button.setProperty("secondary", True)
        self.load_button.style().polish(self.load_button)
        self.load_button.clicked.connect(self.load_config_dialog)
        button_row.addWidget(self.load_button)

        self.save_button = QPushButton("Save Config")
        self.save_button.setProperty("secondary", True)
        self.save_button.style().polish(self.save_button)
        self.save_button.clicked.connect(self.save_config_dialog)
        button_row.addWidget(self.save_button)
        bar_layout.addLayout(button_row)

        aux_row = QHBoxLayout()
        self.reset_button = QPushButton("Reset Defaults")
        self.reset_button.setProperty("secondary", True)
        self.reset_button.style().polish(self.reset_button)
        self.reset_button.clicked.connect(lambda: self.apply_config(core.SimulationConfig()))
        aux_row.addWidget(self.reset_button)

        self.open_outputs_button = QPushButton("Open Output Folder")
        self.open_outputs_button.setProperty("secondary", True)
        self.open_outputs_button.style().polish(self.open_outputs_button)
        self.open_outputs_button.clicked.connect(self.open_output_directory)
        aux_row.addWidget(self.open_outputs_button)
        bar_layout.addLayout(aux_row)

        note = QLabel(
            "Keep coarse scans moderate. The UI will refine automatically so that the "
            "overview figure reaches the target current resolution."
        )
        note.setWordWrap(True)
        note.setProperty("muted", True)
        bar_layout.addWidget(note)
        parent_layout.addWidget(controls_bar)

        info_box = QGroupBox("Rb87 Reference")
        info_layout = QFormLayout(info_box)
        info_layout.setLabelAlignment(Qt.AlignLeft)
        info_layout.setFormAlignment(Qt.AlignTop)
        info_layout.addRow("Transition", QLabel("Rb87 D2, 780.241209 nm"))
        info_layout.addRow("Linewidth", QLabel("6.065 MHz"))
        info_layout.addRow("|gF|", QLabel("0.5 (effective ground-state scale)"))
        info_layout.addRow("Model type", QLabel("Semi-empirical PGC suppression + thermal relaxation"))
        parent_layout.addWidget(info_box)

        self.fields_group, self.static_field_widgets, self.switch_field_widgets = self._build_field_group()
        parent_layout.addWidget(self.fields_group)

        self.molasses_group = self._build_molasses_group()
        parent_layout.addWidget(self.molasses_group)

        self.geometry_group = self._build_geometry_group()
        parent_layout.addWidget(self.geometry_group)

        self.scan_group = self._build_scan_group()
        parent_layout.addWidget(self.scan_group)

        self.refinement_group = self._build_refinement_group()
        parent_layout.addWidget(self.refinement_group)

        self.output_group = self._build_output_group()
        parent_layout.addWidget(self.output_group)

        self.derived_group = self._build_derived_group()
        parent_layout.addWidget(self.derived_group)

    def _build_results_area(self, parent_layout: QVBoxLayout) -> None:
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        self.temperature_card = MetricCard("Final Temperature", accent="#b36a2e")
        self.current_card = MetricCard("Best Current Setpoint", accent="#1b5d73")
        self.field_card = MetricCard("Compensation Field", accent="#4c7240")
        self.resolution_card = MetricCard("Overview Grid Step", accent="#6b5a8b")

        cards_row.addWidget(self.temperature_card)
        cards_row.addWidget(self.current_card)
        cards_row.addWidget(self.field_card)
        cards_row.addWidget(self.resolution_card)
        parent_layout.addLayout(cards_row)

        self.tabs = QTabWidget()
        self.overview_panel = PlotPanel(
            "Overview Map",
            "Temperature slices across the best current neighborhood. This panel uses the final refined grid whenever refinement is enabled.",
        )
        self.dynamics_panel = PlotPanel(
            "Dynamics Trace",
            "Residual magnetic-field evolution and temperature trajectory during optical molasses.",
        )
        self.summary_browser = QTextBrowser()
        self.summary_browser.setOpenExternalLinks(True)
        self.summary_browser.setHtml("<p>Run a simulation to populate the summary report.</p>")

        self.paths_browser = QTextBrowser()
        self.paths_browser.setOpenExternalLinks(True)
        self.paths_browser.setHtml("<p>Run a simulation to see generated output files.</p>")

        self.notes_browser = QTextBrowser()
        self.notes_browser.setOpenExternalLinks(True)
        self.notes_browser.setHtml(self._model_notes_html())

        self.tabs.addTab(self.overview_panel, "Overview")
        self.tabs.addTab(self.dynamics_panel, "Dynamics")
        self.tabs.addTab(self.summary_browser, "Summary")
        self.tabs.addTab(self.paths_browser, "Outputs")
        self.tabs.addTab(self.notes_browser, "Model")
        parent_layout.addWidget(self.tabs, stretch=1)

    def _build_status_bar(self) -> None:
        status = QStatusBar()
        self.setStatusBar(status)
        self.status_label = QLabel("Ready.")
        status.addPermanentWidget(self.status_label, 1)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(220)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        status.addPermanentWidget(self.progress)

    def _build_field_group(self) -> tuple[QGroupBox, dict[str, QDoubleSpinBox], dict[str, QDoubleSpinBox]]:
        group = QGroupBox("Residual Magnetic Fields")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)

        labels = ["X", "Y", "Z"]
        for idx, axis in enumerate(labels, start=1):
            lbl = QLabel(axis)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-weight: 700; color: #36505e;")
            layout.addWidget(lbl, 0, idx)

        static_label = QLabel("Static stray field")
        static_label.setToolTip("Time-independent residual background field seen by the cloud after switch-off transients have vanished.")
        layout.addWidget(static_label, 1, 0)
        static_widgets = {}
        for idx, axis in enumerate(("x", "y", "z"), start=1):
            widget = self._make_double_spin(-5000.0, 5000.0, decimals=3, step=1.0, suffix=" mG")
            widget.valueChanged.connect(self.update_derived_labels)
            layout.addWidget(widget, 1, idx)
            static_widgets[axis] = widget

        switch_label = QLabel("Switch-off residual field")
        switch_label.setToolTip("Transient field present immediately after 3D MOT switch-off, before exponential decay.")
        layout.addWidget(switch_label, 2, 0)
        switch_widgets = {}
        for idx, axis in enumerate(("x", "y", "z"), start=1):
            widget = self._make_double_spin(-5000.0, 5000.0, decimals=3, step=1.0, suffix=" mG")
            widget.valueChanged.connect(self.update_derived_labels)
            layout.addWidget(widget, 2, idx)
            switch_widgets[axis] = widget

        self.mot_decay_spin = self._make_double_spin(0.0, 1000.0, decimals=4, step=0.05, suffix=" ms")
        self.mot_decay_spin.setToolTip("Exponential decay time constant for the switch-off residual field.")
        layout.addWidget(QLabel("Decay time constant"), 3, 0)
        layout.addWidget(self.mot_decay_spin, 3, 1, 1, 3)

        return group, static_widgets, switch_widgets

    def _build_molasses_group(self) -> QGroupBox:
        group = QGroupBox("Molasses Model")
        layout = QFormLayout(group)
        layout.setSpacing(10)

        self.initial_temp_spin = self._make_double_spin(0.0, 1.0e4, decimals=3, step=1.0, suffix=" uK")
        self.zero_field_temp_spin = self._make_double_spin(0.0, 1.0e4, decimals=3, step=0.5, suffix=" uK")
        self.failure_temp_spin = self._make_double_spin(0.0, 1.0e4, decimals=3, step=1.0, suffix=" uK")
        self.duration_spin = self._make_double_spin(0.01, 1000.0, decimals=4, step=0.1, suffix=" ms")
        self.time_step_spin = self._make_double_spin(0.1, 10000.0, decimals=2, step=5.0, suffix=" us")
        self.zero_field_cooling_time_spin = self._make_double_spin(0.001, 1000.0, decimals=4, step=0.05, suffix=" ms")
        self.detuning_spin = self._make_double_spin(-500.0, 500.0, decimals=3, step=0.5, suffix=" MHz")
        self.saturation_spin = self._make_double_spin(0.0, 100.0, decimals=4, step=0.02)
        self.beams_spin = self._make_int_spin(1, 12, step=1)
        self.optical_pumping_spin = self._make_double_spin(0.001, 1000.0, decimals=4, step=0.05)
        self.minimum_efficiency_spin = self._make_double_spin(0.0, 1.0, decimals=4, step=0.01)
        self.magnetic_width_override_spin = self._make_double_spin(0.0, 10000.0, decimals=4, step=1.0, suffix=" mG")
        self.use_width_override = QCheckBox("Use explicit magnetic-width override")
        self.use_width_override.toggled.connect(self.magnetic_width_override_spin.setEnabled)
        self.use_width_override.toggled.connect(self.update_derived_labels)
        self.magnetic_width_override_spin.setEnabled(False)
        self.magnetic_width_override_spin.valueChanged.connect(self.update_derived_labels)

        layout.addRow("Initial temperature", self.initial_temp_spin)
        layout.addRow("Zero-field temperature limit", self.zero_field_temp_spin)
        layout.addRow("High-field failure temperature", self.failure_temp_spin)
        layout.addRow("Molasses duration", self.duration_spin)
        layout.addRow("Simulation time step", self.time_step_spin)
        layout.addRow("Zero-field cooling time", self.zero_field_cooling_time_spin)
        layout.addRow("Detuning", self.detuning_spin)
        layout.addRow("Saturation per beam", self.saturation_spin)
        layout.addRow("Number of beams", self.beams_spin)
        layout.addRow("Optical-pumping width scale", self.optical_pumping_spin)
        layout.addRow("Minimum relative efficiency", self.minimum_efficiency_spin)
        layout.addRow(self.use_width_override, self.magnetic_width_override_spin)
        return group

    def _build_geometry_group(self) -> QGroupBox:
        group = QGroupBox("Coil Geometry")
        layout = QFormLayout(group)
        layout.setSpacing(10)
        self.turns_spin = self._make_int_spin(1, 500, step=1)
        self.side_length_spin = self._make_double_spin(0.1, 500.0, decimals=4, step=1.0, suffix=" cm")
        self.center_to_coil_spin = self._make_double_spin(0.1, 500.0, decimals=4, step=1.0, suffix=" cm")

        for widget in (self.turns_spin, self.side_length_spin, self.center_to_coil_spin):
            widget.valueChanged.connect(self.update_derived_labels)

        layout.addRow("Turns per coil", self.turns_spin)
        layout.addRow("Square side length", self.side_length_spin)
        layout.addRow("Center to each coil", self.center_to_coil_spin)
        return group

    def _build_scan_group(self) -> QGroupBox:
        group = QGroupBox("Coarse Current Scan")
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)

        headers = ["Start", "Stop", "Points"]
        for idx, text in enumerate(headers, start=1):
            label = QLabel(text)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-weight: 700; color: #36505e;")
            layout.addWidget(label, 0, idx)

        self.scan_widgets: dict[str, tuple[QDoubleSpinBox, QDoubleSpinBox, QSpinBox]] = {}
        for row, axis in enumerate(("X", "Y", "Z"), start=1):
            layout.addWidget(QLabel(f"{axis} current"), row, 0)
            start_widget = self._make_double_spin(-50.0, 50.0, decimals=4, step=0.1, suffix=" A")
            stop_widget = self._make_double_spin(-50.0, 50.0, decimals=4, step=0.1, suffix=" A")
            points_widget = self._make_int_spin(2, 2000, step=1)
            for widget in (start_widget, stop_widget, points_widget):
                widget.valueChanged.connect(self.update_derived_labels)
            layout.addWidget(start_widget, row, 1)
            layout.addWidget(stop_widget, row, 2)
            layout.addWidget(points_widget, row, 3)
            self.scan_widgets[axis.lower()] = (start_widget, stop_widget, points_widget)

        return group

    def _build_refinement_group(self) -> QGroupBox:
        group = QGroupBox("Overview Resolution and Refinement")
        layout = QFormLayout(group)
        layout.setSpacing(10)
        self.refinement_enabled = QCheckBox("Enable local refinement for overview and best-point search")
        self.refinement_enabled.toggled.connect(self.update_derived_labels)
        self.refinement_steps_spin = self._make_int_spin(1, 10, step=1)
        self.refinement_points_spin = self._make_int_spin(3, 4000, step=2)
        self.target_step_spin = self._make_double_spin(0.0001, 10.0, decimals=4, step=0.005, suffix=" A")

        self.refinement_steps_spin.valueChanged.connect(self.update_derived_labels)
        self.refinement_points_spin.valueChanged.connect(self.update_derived_labels)
        self.target_step_spin.valueChanged.connect(self.update_derived_labels)

        layout.addRow(self.refinement_enabled)
        layout.addRow("Max refinement stages", self.refinement_steps_spin)
        layout.addRow("Minimum points per axis", self.refinement_points_spin)
        layout.addRow("Target overview step", self.target_step_spin)
        return group

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox("Output Naming")
        layout = QFormLayout(group)
        layout.setSpacing(10)
        self.output_directory_edit = QLineEdit()
        self.output_prefix_edit = QLineEdit()
        self.output_directory_edit.textChanged.connect(self.update_derived_labels)
        self.output_prefix_edit.textChanged.connect(self.update_derived_labels)

        layout.addRow("Output directory", self.output_directory_edit)
        layout.addRow("File prefix", self.output_prefix_edit)
        return group

    def _build_derived_group(self) -> QGroupBox:
        group = QGroupBox("Derived Quantities")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self.derived_field_label = QLabel("--")
        self.derived_field_label.setWordWrap(True)
        self.derived_width_label = QLabel("--")
        self.derived_width_label.setWordWrap(True)
        self.derived_scan_label = QLabel("--")
        self.derived_scan_label.setWordWrap(True)

        for label in (self.derived_field_label, self.derived_width_label, self.derived_scan_label):
            label.setStyleSheet(
                "background: #faf8f3; border: 1px solid #ddd8ce; border-radius: 12px; padding: 10px;"
            )
            layout.addWidget(label)
        return group

    def _make_double_spin(
        self,
        minimum: float,
        maximum: float,
        *,
        decimals: int,
        step: float,
        suffix: str = "",
    ) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(decimals)
        widget.setSingleStep(step)
        widget.setSuffix(suffix)
        widget.setAccelerated(True)
        return widget

    def _make_int_spin(self, minimum: int, maximum: int, *, step: int) -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setSingleStep(step)
        widget.setAccelerated(True)
        return widget

    def current_config(self) -> core.SimulationConfig:
        magnetic_width_override = None
        if self.use_width_override.isChecked():
            magnetic_width_override = float(self.magnetic_width_override_spin.value())

        scan_x = self.scan_widgets["x"]
        scan_y = self.scan_widgets["y"]
        scan_z = self.scan_widgets["z"]

        return core.SimulationConfig(
            atom=core.AtomConfig(),
            molasses=core.MolassesConfig(
                initial_temperature_uK=float(self.initial_temp_spin.value()),
                zero_field_temperature_uK=float(self.zero_field_temp_spin.value()),
                failure_temperature_uK=float(self.failure_temp_spin.value()),
                molasses_duration_ms=float(self.duration_spin.value()),
                time_step_us=float(self.time_step_spin.value()),
                zero_field_cooling_time_ms=float(self.zero_field_cooling_time_spin.value()),
                detuning_mhz=float(self.detuning_spin.value()),
                saturation_parameter_per_beam=float(self.saturation_spin.value()),
                number_of_beams=int(self.beams_spin.value()),
                optical_pumping_width_scale=float(self.optical_pumping_spin.value()),
                minimum_relative_efficiency=float(self.minimum_efficiency_spin.value()),
                magnetic_width_mG_override=magnetic_width_override,
            ),
            fields=core.FieldConfig(
                static_stray_field_mG=(
                    float(self.static_field_widgets["x"].value()),
                    float(self.static_field_widgets["y"].value()),
                    float(self.static_field_widgets["z"].value()),
                ),
                mot_switch_off_field_mG=(
                    float(self.switch_field_widgets["x"].value()),
                    float(self.switch_field_widgets["y"].value()),
                    float(self.switch_field_widgets["z"].value()),
                ),
                mot_decay_tau_ms=float(self.mot_decay_spin.value()),
            ),
            coil_geometry=core.CoilGeometryConfig(
                turns_per_coil=int(self.turns_spin.value()),
                side_length_cm=float(self.side_length_spin.value()),
                center_to_coil_cm=float(self.center_to_coil_spin.value()),
            ),
            scan=core.CurrentScanConfig(
                x_current_A=core.AxisScan(
                    start=float(scan_x[0].value()),
                    stop=float(scan_x[1].value()),
                    points=int(scan_x[2].value()),
                ),
                y_current_A=core.AxisScan(
                    start=float(scan_y[0].value()),
                    stop=float(scan_y[1].value()),
                    points=int(scan_y[2].value()),
                ),
                z_current_A=core.AxisScan(
                    start=float(scan_z[0].value()),
                    stop=float(scan_z[1].value()),
                    points=int(scan_z[2].value()),
                ),
            ),
            refinement=core.RefinementConfig(
                enabled=bool(self.refinement_enabled.isChecked()),
                steps=int(self.refinement_steps_spin.value()),
                points_per_axis=int(self.refinement_points_spin.value()),
                target_step_A=float(self.target_step_spin.value()),
            ),
            output=core.OutputConfig(
                directory=self.output_directory_edit.text().strip() or "outputs",
                prefix=self.output_prefix_edit.text().strip() or "rb87_pgc_current_scan",
            ),
        )

    def apply_config(self, config: core.SimulationConfig) -> None:
        self.initial_temp_spin.setValue(config.molasses.initial_temperature_uK)
        self.zero_field_temp_spin.setValue(config.molasses.zero_field_temperature_uK)
        self.failure_temp_spin.setValue(config.molasses.failure_temperature_uK)
        self.duration_spin.setValue(config.molasses.molasses_duration_ms)
        self.time_step_spin.setValue(config.molasses.time_step_us)
        self.zero_field_cooling_time_spin.setValue(config.molasses.zero_field_cooling_time_ms)
        self.detuning_spin.setValue(config.molasses.detuning_mhz)
        self.saturation_spin.setValue(config.molasses.saturation_parameter_per_beam)
        self.beams_spin.setValue(config.molasses.number_of_beams)
        self.optical_pumping_spin.setValue(config.molasses.optical_pumping_width_scale)
        self.minimum_efficiency_spin.setValue(config.molasses.minimum_relative_efficiency)

        override = config.molasses.magnetic_width_mG_override
        self.use_width_override.setChecked(override is not None)
        self.magnetic_width_override_spin.setEnabled(override is not None)
        self.magnetic_width_override_spin.setValue(0.0 if override is None else override)

        for axis, value in zip(("x", "y", "z"), config.fields.static_stray_field_mG):
            self.static_field_widgets[axis].setValue(value)
        for axis, value in zip(("x", "y", "z"), config.fields.mot_switch_off_field_mG):
            self.switch_field_widgets[axis].setValue(value)
        self.mot_decay_spin.setValue(config.fields.mot_decay_tau_ms)

        self.turns_spin.setValue(config.coil_geometry.turns_per_coil)
        self.side_length_spin.setValue(config.coil_geometry.side_length_cm)
        self.center_to_coil_spin.setValue(config.coil_geometry.center_to_coil_cm)

        for axis, axis_scan in zip(
            ("x", "y", "z"),
            (config.scan.x_current_A, config.scan.y_current_A, config.scan.z_current_A),
        ):
            start_widget, stop_widget, points_widget = self.scan_widgets[axis]
            start_widget.setValue(axis_scan.start)
            stop_widget.setValue(axis_scan.stop)
            points_widget.setValue(axis_scan.points)

        self.refinement_enabled.setChecked(config.refinement.enabled)
        self.refinement_steps_spin.setValue(config.refinement.steps)
        self.refinement_points_spin.setValue(config.refinement.points_per_axis)
        self.target_step_spin.setValue(config.refinement.target_step_A)

        self.output_directory_edit.setText(config.output.directory)
        self.output_prefix_edit.setText(config.output.prefix)
        self.update_derived_labels()

    def update_derived_labels(self) -> None:
        config = self.current_config()
        field_per_amp = core.square_pair_center_field_mG_per_A(config.coil_geometry)
        magnetic_width = core.magnetic_width_mG(config)

        coarse_steps = {
            "x": core.axis_step(config.scan.x_current_A.values()),
            "y": core.axis_step(config.scan.y_current_A.values()),
            "z": core.axis_step(config.scan.z_current_A.values()),
        }

        if config.refinement.enabled:
            overview_step = min(config.refinement.target_step_A, max(coarse_steps.values()))
            refinement_note = (
                f"Refinement enabled, target overview step <= {config.refinement.target_step_A:.4f} A "
                f"with up to {config.refinement.steps} stage(s)."
            )
        else:
            overview_step = max(coarse_steps.values())
            refinement_note = "Refinement disabled, overview figure will use the coarse-grid step."

        self.derived_field_label.setText(
            "Center-field conversion\n"
            f"1 A -> {field_per_amp:.6f} mG for each ideal axis pair\n"
            f"Coil geometry: {config.coil_geometry.turns_per_coil} turns, "
            f"{config.coil_geometry.side_length_cm:.2f} cm square, "
            f"{config.coil_geometry.center_to_coil_cm:.2f} cm offset."
        )
        self.derived_width_label.setText(
            "Cooling-width estimate\n"
            f"Magnetic width B_width = {magnetic_width:.6f} mG\n"
            f"Detuning = {config.molasses.detuning_mhz:.3f} MHz, "
            f"s_per_beam = {config.molasses.saturation_parameter_per_beam:.4f}, "
            f"beams = {config.molasses.number_of_beams}."
        )
        self.derived_scan_label.setText(
            "Scan and overview resolution\n"
            f"Coarse steps: dIx = {coarse_steps['x']:.4f} A, "
            f"dIy = {coarse_steps['y']:.4f} A, dIz = {coarse_steps['z']:.4f} A\n"
            f"Expected overview step: about {overview_step:.4f} A\n"
            f"{refinement_note}"
        )

    def run_simulation(self) -> None:
        if self.worker_thread is not None:
            QMessageBox.information(self, "Simulation Running", "A simulation is already in progress.")
            return

        config = self.current_config()
        self._set_busy_state(True, "Preparing simulation...")

        self.worker_thread = QThread()
        self.worker = SimulationWorker(config)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.status.connect(self._set_status_message)
        self.worker.finished.connect(self._on_simulation_finished)
        self.worker.error.connect(self._on_simulation_error)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.error.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._cleanup_worker)
        self.worker_thread.start()

    def _on_simulation_finished(self, bundle: object) -> None:
        self.last_bundle = bundle
        bundle_dict = bundle
        best_result = bundle_dict["best_result"]
        refinement_result = bundle_dict["refinement_result"]
        config = bundle_dict["config"]

        self.overview_panel.set_image(bundle_dict["paths"]["overview"])
        self.dynamics_panel.set_image(bundle_dict["paths"]["dynamics"])

        summary_text = Path(bundle_dict["paths"]["summary"]).read_text(encoding="utf-8")
        self.summary_browser.setPlainText(summary_text)
        self.paths_browser.setHtml(self._paths_html(bundle_dict))

        field_per_amp = core.square_pair_center_field_mG_per_A(config.coil_geometry)
        coarse_step_x = core.axis_step(bundle_dict["coarse_result"]["x_currents"])
        if refinement_result is not None and refinement_result.get("final_grid") is not None:
            final_grid = refinement_result["final_grid"]
            overview_step = max(
                core.axis_step(final_grid["x_currents"]),
                core.axis_step(final_grid["y_currents"]),
                core.axis_step(final_grid["z_currents"]),
            )
        else:
            overview_step = coarse_step_x

        self.temperature_card.set_text(
            f"{best_result['final_temperature_uK']:.4f} uK",
            f"Cooling efficiency = {best_result['cooling_efficiency']:.4f}",
        )
        self.current_card.set_text(
            "("
            f"{best_result['current_xyz_A'][0]:.4f}, "
            f"{best_result['current_xyz_A'][1]:.4f}, "
            f"{best_result['current_xyz_A'][2]:.4f}"
            ") A",
            "Best current triplet from the final search grid.",
        )
        self.field_card.set_text(
            "("
            f"{best_result['coil_field_mG'][0]:.2f}, "
            f"{best_result['coil_field_mG'][1]:.2f}, "
            f"{best_result['coil_field_mG'][2]:.2f}"
            ") mG",
            f"Center-field conversion = {field_per_amp:.3f} mG/A",
        )
        self.resolution_card.set_text(
            f"{overview_step:.4f} A",
            f"Coarse dI = {coarse_step_x:.4f} A; overview uses the final grid shown on the map.",
        )

        self._set_busy_state(False, "Simulation complete.")
        self.tabs.setCurrentWidget(self.overview_panel)

    def _on_simulation_error(self, trace_text: str) -> None:
        self._set_busy_state(False, "Simulation failed.")
        QMessageBox.critical(self, "Simulation Failed", trace_text)

    def _cleanup_worker(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
        if self.worker_thread is not None:
            self.worker_thread.deleteLater()
            self.worker_thread = None

    def _set_busy_state(self, busy: bool, message: str) -> None:
        self.run_button.setEnabled(not busy)
        self.load_button.setEnabled(not busy)
        self.save_button.setEnabled(not busy)
        self.reset_button.setEnabled(not busy)
        self.progress.setRange(0, 0 if busy else 1)
        if not busy:
            self.progress.setValue(1)
        self._set_status_message(message)

    def _set_status_message(self, text: str) -> None:
        self.status_label.setText(text)

    def load_config_dialog(self) -> None:
        path_text, _ = QFileDialog.getOpenFileName(
            self,
            "Load Simulation Config",
            str(Path(core.__file__).resolve().parent),
            "JSON Files (*.json)",
        )
        if not path_text:
            return
        config = core.load_config(Path(path_text))
        self.apply_config(config)
        self._set_status_message(f"Loaded config: {path_text}")

    def save_config_dialog(self) -> None:
        path_text, _ = QFileDialog.getSaveFileName(
            self,
            "Save Simulation Config",
            str(Path(core.__file__).resolve().parent / "ui_config.json"),
            "JSON Files (*.json)",
        )
        if not path_text:
            return
        config = self.current_config()
        Path(path_text).write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
        self._set_status_message(f"Saved config: {path_text}")

    def open_output_directory(self) -> None:
        if self.last_bundle is not None:
            path = self.last_bundle["paths"]["output_dir"]
        else:
            path = Path(core.__file__).resolve().parent / self.current_config().output.directory
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _paths_html(self, bundle: dict) -> str:
        paths = bundle["paths"]
        lines = [
            "<h3>Generated Outputs</h3>",
            "<p>The simulation writes the same outputs as the command-line version, so the GUI remains numerically aligned with the scripted workflow.</p>",
            "<ul>",
        ]
        for label, key in (
            ("Output directory", "output_dir"),
            ("Coarse scan CSV", "csv"),
            ("Refined scan CSV", "refined_csv"),
            ("Overview figure", "overview"),
            ("Dynamics figure", "dynamics"),
            ("Summary text", "summary"),
            ("Resolved config", "resolved_config"),
        ):
            path = paths.get(key)
            if path is None:
                continue
            url = QUrl.fromLocalFile(str(path)).toString()
            lines.append(f"<li><b>{label}:</b> <a href='{url}'>{path}</a></li>")
        lines.append("</ul>")
        return "".join(lines)

    def _model_notes_html(self) -> str:
        return """
        <h3>Model Notes</h3>
        <p><b>This UI uses the same simulation core as the command-line tool.</b> It is designed for experimental scan planning and calibration, not as a full quantum-optical Monte Carlo solver.</p>
        <p><b>Residual field model</b><br>
        <code>B(t) = B_stray + B_coil + B_switch_off exp(-t / tau)</code></p>
        <p><b>Cooling-efficiency suppression</b><br>
        <code>eta(t) = 1 / [1 + (|B(t)| / B_width)^2]</code></p>
        <p><b>Temperature evolution</b><br>
        <code>dT/dt = -(T - T_eq(B)) / tau_cool(B)</code></p>
        <p>Key interpretation:</p>
        <ul>
        <li><b>Static stray field</b> is the long-lived background field after switch-off transients vanish.</li>
        <li><b>Switch-off residual field</b> is the transient field present at the beginning of molasses.</li>
        <li><b>Target overview step</b> controls the final current-grid spacing shown in the overview figure when local refinement is enabled.</li>
        </ul>
        <p>Use the GUI to tune parameters quickly, then keep the exported JSON and CSV outputs as your reproducible record.</p>
        """


def launch() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Rb87 Bias-Coil Molasses Simulator")
    app.setFont(QFont("Aptos", 10))
    window = BiasCoilsCurrentScanWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(launch())
