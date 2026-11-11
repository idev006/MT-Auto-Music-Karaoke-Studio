"""Native-theme PySide6 batch monitor for the headless karaoke engine."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QLocale, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionProgressBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from mt_engine.application import (
    ApplicationOrchestrator,
    BatchJobSnapshot,
    BatchSettings,
)
from mt_engine.paths import PathManager
from mt_engine.presentation.numbers import ascii_digits
from mt_engine.production.karaoke_presets import list_karaoke_presets


class JobTableModel(QAbstractTableModel):
    HEADERS = (
        "งาน",
        "โฟลเดอร์ต้นทาง",
        "สถานะ",
        "ความคืบหน้า",
        "รายละเอียด",
        "ข้อมูล FFmpeg",
        "ผลลัพธ์",
    )

    def __init__(self) -> None:
        super().__init__()
        self._rows: tuple[BatchJobSnapshot, ...] = ()

    def replace(self, rows: tuple[BatchJobSnapshot, ...]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent=None) -> int:
        return 0 if parent is not None and parent.isValid() else len(self._rows)

    def columnCount(self, parent=None) -> int:
        return 0 if parent is not None and parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        job = self._rows[index.row()]
        if role == Qt.UserRole:
            return job.progress if index.column() == 3 else job.job_id
        if role == Qt.ToolTipRole:
            return job.error or str(job.target or job.source)
        if role != Qt.DisplayRole:
            return None
        values = (
            job.job_id,
            str(job.source),
            job.state.value,
            f"{ascii_digits(job.progress)}%",
            job.error or job.detail,
            "  ".join(f"{key}={value}" for key, value in job.metrics),
            str(job.target or ""),
        )
        return ascii_digits(values[index.column()])

    def job_id(self, row: int) -> str:
        return self._rows[row].job_id

    def job(self, row: int) -> BatchJobSnapshot:
        return self._rows[row]


class ProgressDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        value = int(index.data(Qt.UserRole) or 0)
        progress = QStyleOptionProgressBar()
        progress.rect = option.rect.adjusted(4, 4, -4, -4)
        progress.minimum = 0
        progress.maximum = 100
        progress.progress = value
        progress.text = f"{ascii_digits(value)}%"
        progress.textVisible = True
        QApplication.style().drawControl(QStyle.CE_ProgressBar, progress, painter)


class MainWindow(QMainWindow):
    def __init__(self, paths: PathManager) -> None:
        super().__init__()
        self.paths = paths
        self.orchestrator = ApplicationOrchestrator()
        self._event_cursor = 0
        PathManager.output_root(self.paths.data_root)
        self.settings = QSettings(str(self.paths.data("settings.ini")), QSettings.Format.IniFormat)
        self.setWindowTitle("MT Auto Music & Karaoke Studio")
        self.resize(1280, 760)
        self.setAcceptDrops(True)
        self._build_ui()
        self._load_settings()
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self._refresh)
        self.timer.start()
        self._refresh(force=True)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        heading = QLabel("คิวผลิตเพลงและคาราโอเกะ")
        heading_font = heading.font()
        heading_font.setPointSize(16)
        heading_font.setBold(True)
        heading.setFont(heading_font)
        layout.addWidget(heading)
        layout.addWidget(QLabel("หนึ่ง worker รับผิดชอบหนึ่งโฟลเดอร์ งานแต่ละรายการแยกจากกัน"))

        settings_box = QGroupBox("การตั้งค่า Engine")
        form = QGridLayout(settings_box)
        self.dest_edit = self._path_row(form, 0, "โฟลเดอร์ผลลัพธ์", self._browse_dest)
        self.ffmpeg_edit = self._path_row(form, 1, "FFmpeg root", self._browse_ffmpeg)
        self.fonts_edit = self._path_row(form, 2, "Font assets", self._browse_fonts)
        self.lock_edit = self._path_row(form, 3, "Timing lock (ถ้ามี)", self._browse_lock)

        options = QWidget()
        options_layout = QFormLayout(options)
        self.worker_spin = QSpinBox()
        self.worker_spin.setRange(1, max(1, min(32, os.cpu_count() or 4)))
        self.worker_spin.setLocale(QLocale.c())
        self.cpu_spin = QSpinBox()
        self.cpu_spin.setRange(1, max(1, os.cpu_count() or 4))
        self.cpu_spin.setLocale(QLocale.c())
        self.model_combo = QComboBox()
        self.model_combo.addItems(("base", "small", "medium", "large-v3"))
        self.preset_combo = QComboBox()
        for preset in list_karaoke_presets():
            self.preset_combo.addItem(str(preset["display_name"]), str(preset["preset_id"]))
        self.router_combo = QComboBox()
        self.router_combo.addItems(("off", "auto", "always"))
        self.unreviewed_check = QCheckBox("สร้างวิดีโอทดสอบเมื่อ timing ยังไม่ผ่านการ review")
        options_layout.addRow("จำนวน worker", self.worker_spin)
        options_layout.addRow("CPU threads ต่อ worker", self.cpu_spin)
        options_layout.addRow("Whisper model", self.model_combo)
        options_layout.addRow("Karaoke preset", self.preset_combo)
        options_layout.addRow("OpenRouter", self.router_combo)
        options_layout.addRow("", self.unreviewed_check)
        form.addWidget(options, 0, 3, 4, 1)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)
        layout.addWidget(settings_box)

        actions = QHBoxLayout()
        self.add_button = QPushButton("เพิ่มโฟลเดอร์")
        self.remove_button = QPushButton("ลบรายการที่เลือก")
        self.start_button = QPushButton("เริ่มประมวลผล")
        self.cancel_button = QPushButton("ยกเลิกงานที่เลือก")
        self.details_button = QPushButton("ดูรายละเอียด")
        self.open_output_button = QPushButton("เปิดโฟลเดอร์ผลลัพธ์")
        self.add_button.clicked.connect(self._add_folder)
        self.remove_button.clicked.connect(self._remove_selected)
        self.start_button.clicked.connect(self._start)
        self.cancel_button.clicked.connect(self._cancel_selected)
        self.details_button.clicked.connect(self._show_selected_details)
        self.open_output_button.clicked.connect(self._open_selected_output)
        actions.addWidget(self.add_button)
        actions.addWidget(self.remove_button)
        actions.addStretch(1)
        actions.addWidget(self.details_button)
        actions.addWidget(self.open_output_button)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.start_button)
        layout.addLayout(actions)

        self.model = JobTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._show_job_details)
        self.table.setItemDelegateForColumn(3, ProgressDelegate(self.table))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)
        self.status_label = QLabel("พร้อม")
        layout.addWidget(self.status_label)
        self.setCentralWidget(root)

    def _path_row(self, layout, row: int, label: str, callback):
        edit = QLineEdit()
        button = QPushButton("เลือก…")
        button.clicked.connect(callback)
        layout.addWidget(QLabel(label), row, 0)
        layout.addWidget(edit, row, 1)
        layout.addWidget(button, row, 2)
        return edit

    def _choose_dir(self, title: str, edit: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(self, title, edit.text())
        if selected:
            edit.setText(str(Path(selected).resolve()))

    def _browse_dest(self):
        self._choose_dir("เลือกโฟลเดอร์ผลลัพธ์", self.dest_edit)

    def _browse_ffmpeg(self):
        self._choose_dir("เลือก FFmpeg root", self.ffmpeg_edit)

    def _browse_fonts(self):
        self._choose_dir("เลือกโฟลเดอร์ฟอนต์", self.fonts_edit)

    def _browse_lock(self):
        selected, _ = QFileDialog.getOpenFileName(
            self, "เลือก timing lock", self.lock_edit.text(), "JSON (*.json)"
        )
        if selected:
            self.lock_edit.setText(str(Path(selected).resolve()))

    def _add_folder(self):
        selected = QFileDialog.getExistingDirectory(self, "เพิ่มโฟลเดอร์เพลง")
        if selected:
            self._add_paths((Path(selected),))

    def _add_paths(self, paths: tuple[Path, ...]) -> None:
        try:
            self.orchestrator.add(paths)
        except (RuntimeError, ValueError) as error:
            QMessageBox.warning(self, "เพิ่มโฟลเดอร์ไม่ได้", str(error))
        self._refresh()

    def _selected_ids(self) -> tuple[str, ...]:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        return tuple(self.model.job_id(row) for row in rows)

    def _selection_changed(self, *_args) -> None:
        has_selection = bool(self._selected_ids())
        self.details_button.setEnabled(has_selection)
        self.open_output_button.setEnabled(has_selection)

    def _remove_selected(self):
        try:
            self.orchestrator.remove_queued(self._selected_ids())
        except RuntimeError as error:
            QMessageBox.warning(self, "ลบรายการไม่ได้", str(error))
        self._refresh()

    def _cancel_selected(self):
        selected = self._selected_ids()
        if not selected:
            self.orchestrator.cancel_all()
        else:
            self.orchestrator.cancel(selected)
        self._refresh()

    def _selected_job(self) -> BatchJobSnapshot | None:
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        return self.model.job(rows[0]) if rows else None

    def _show_selected_details(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self._show_job_details(rows[0])

    def _show_job_details(self, index) -> None:
        if not index.isValid():
            return
        job = self.model.job(index.row())
        message = QMessageBox(self)
        message.setWindowTitle(f"รายละเอียด {job.job_id}")
        message.setIcon(QMessageBox.Critical if job.error else QMessageBox.Information)
        message.setText(job.error or job.detail)
        message.setInformativeText(
            f"ต้นทาง: {job.source}\nผลลัพธ์: {job.target or '-'}"
        )
        if job.error_detail:
            message.setDetailedText(job.error_detail)
        message.exec()

    def _open_selected_output(self) -> None:
        job = self._selected_job()
        target = job.target if job is not None else None
        if target is None or not target.exists():
            QMessageBox.information(self, "ยังไม่มีผลลัพธ์", "งานนี้ยังไม่มีโฟลเดอร์ผลลัพธ์")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _start(self):
        try:
            self._save_settings()
            lock_text = self.lock_edit.text().strip()
            settings = BatchSettings(
                dest_root=Path(self.dest_edit.text()),
                ffmpeg_root=Path(self.ffmpeg_edit.text()),
                font_assets_dir=Path(self.fonts_edit.text()),
                model_cache_dir=self.paths.model_cache("faster-whisper"),
                model_name=self.model_combo.currentText(),
                cpu_threads_per_worker=self.cpu_spin.value(),
                karaoke_preset=str(self.preset_combo.currentData()),
                openrouter_config=self.paths.app("config", "openrouter.env"),
                openrouter_mode=self.router_combo.currentText(),
                accept_unreviewed_timing=self.unreviewed_check.isChecked(),
                timing_lock=Path(lock_text) if lock_text else None,
            )
            self.orchestrator.start(settings, max_workers=self.worker_spin.value())
        except (OSError, RuntimeError, ValueError) as error:
            QMessageBox.critical(self, "เริ่มงานไม่ได้", str(error))
        self._refresh()

    def _refresh(self, force: bool = False):
        events, self._event_cursor = self.orchestrator.events_since(self._event_cursor)
        if not force and not events:
            return
        view = self.orchestrator.view()
        self.model.replace(view.jobs)
        self.status_label.setText(
            f"ทั้งหมด {ascii_digits(view.total_jobs)}  "
            f"กำลังทำงาน {ascii_digits(view.active_jobs)}  "
            f"สิ้นสุด {ascii_digits(view.terminal_jobs)}"
        )
        self.start_button.setEnabled(view.can_start)
        self.add_button.setEnabled(view.queue_mutable)
        self.remove_button.setEnabled(view.queue_mutable)
        self.worker_spin.setEnabled(view.queue_mutable)
        self.cpu_spin.setEnabled(view.queue_mutable)
        has_selection = bool(self._selected_ids())
        self.details_button.setEnabled(has_selection)
        self.open_output_button.setEnabled(has_selection)

    def _load_settings(self) -> None:
        self.dest_edit.setText(str(self.settings.value("dest", self.paths.data("outputs"))))
        bundled_ffmpeg = self.paths.app("ffmpeg")
        default_ffmpeg = os.environ.get("MT_FFMPEG_ROOT", "")
        if bundled_ffmpeg.is_dir():
            default_ffmpeg = str(bundled_ffmpeg)
        self.ffmpeg_edit.setText(str(self.settings.value("ffmpeg", default_ffmpeg)))
        self.fonts_edit.setText(
            str(self.settings.value("fonts", self.paths.bundle("assets", "Fonts")))
        )
        self.worker_spin.setValue(int(self.settings.value("workers", 1)))
        self.cpu_spin.setValue(int(self.settings.value("cpu_threads", 2)))
        diagnostic_value = str(self.settings.value("diagnostic_timing", "true")).lower()
        self.unreviewed_check.setChecked(diagnostic_value in {"1", "true", "yes"})

    def _save_settings(self) -> None:
        self.settings.setValue("dest", self.dest_edit.text())
        self.settings.setValue("ffmpeg", self.ffmpeg_edit.text())
        self.settings.setValue("fonts", self.fonts_edit.text())
        self.settings.setValue("workers", self.worker_spin.value())
        self.settings.setValue("cpu_threads", self.cpu_spin.value())
        self.settings.setValue("diagnostic_timing", self.unreviewed_check.isChecked())

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() and any(
            Path(url.toLocalFile()).is_dir() for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        folders = tuple(
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if Path(url.toLocalFile()).is_dir()
        )
        self._add_paths(folders)
        event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent):
        if self.orchestrator.is_running():
            QMessageBox.warning(
                self,
                "ยังปิดไม่ได้",
                "ยังมีงานกำลังใช้ทรัพยากร กรุณายกเลิกและรอให้งานสิ้นสุดก่อนปิดโปรแกรม",
            )
            event.ignore()
            return
        self.orchestrator.shutdown(wait=False)
        event.accept()


def main() -> int:
    QLocale.setDefault(QLocale.c())
    app = QApplication(sys.argv)
    app.setApplicationName("MT Auto Music & Karaoke Studio")
    app.setOrganizationName("MT")
    window = MainWindow(PathManager.detect())
    window.show()
    if "--smoke-test" in sys.argv:
        QTimer.singleShot(250, window.close)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
