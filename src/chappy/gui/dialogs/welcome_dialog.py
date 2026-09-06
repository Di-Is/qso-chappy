"""First-run welcome dialog offering the bundled sample spectrum."""

from __future__ import annotations

from enum import Enum, auto

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from chappy.gui.dialog_sizing import enforce_translated_minimum_size
from chappy.gui.theme import apply_action_row_sizing, apply_button_variant
from chappy.gui.visual_tokens import DialogMetrics


class WelcomeDialog(QDialog):
    """Welcome dialog shown on first launch and from Help > Tutorial.

    Offers to open the bundled sample spectrum so new users can walk
    through the analysis workflow with data that has a known absorber.
    """

    class Choice(Enum):
        """Possible outcomes of the welcome dialog."""

        START_ESSENTIAL_WALKTHROUGH = auto()
        START_ADVANCED_WALKTHROUGH = auto()
        DISMISS = auto()

    def __init__(self, parent: QWidget | None = None, *, sample_available: bool = True) -> None:
        """Initialize the dialog.

        Args:
            parent: Parent widget for the dialog.
            sample_available: Whether the bundled sample spectrum was found.
        """
        super().__init__(parent)
        self._choice = WelcomeDialog.Choice.DISMISS
        self._sample_available = sample_available

        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self._build_ui()
        self._wire_signals()
        self._retranslate_ui()

    @property
    def choice(self) -> WelcomeDialog.Choice:
        """Return the user's selected action.

        Returns:
            Selected welcome action.
        """
        return self._choice

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Retranslate the dialog when Qt translators change.

        Args:
            event: Qt change event delivered to the dialog.
        """
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate_ui()
        super().changeEvent(event)

    def _build_ui(self) -> None:
        """Build the static widget tree for the dialog."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        self._greeting_label = QLabel(self)
        self._greeting_label.setWordWrap(True)
        self._greeting_label.setObjectName("welcomeGreeting")
        layout.addWidget(self._greeting_label)

        self._workflow_label = QLabel(self)
        self._workflow_label.setWordWrap(True)
        self._workflow_label.setObjectName("welcomeWorkflow")
        layout.addWidget(self._workflow_label)

        self._sample_intro_label = QLabel(self)
        self._sample_intro_label.setWordWrap(True)
        self._sample_intro_label.setObjectName("welcomeSampleIntro")
        layout.addWidget(self._sample_intro_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)

        self._advanced_walkthrough_button = QPushButton(self)
        self._advanced_walkthrough_button.setDefault(False)
        self._advanced_walkthrough_button.setAutoDefault(False)
        apply_button_variant(self._advanced_walkthrough_button, "secondary")
        self._advanced_walkthrough_button.setEnabled(self._sample_available)

        self._essential_walkthrough_button = QPushButton(self)
        self._essential_walkthrough_button.setDefault(True)
        self._essential_walkthrough_button.setAutoDefault(True)
        apply_button_variant(self._essential_walkthrough_button, "primary")
        self._essential_walkthrough_button.setEnabled(self._sample_available)

        apply_action_row_sizing(
            self._advanced_walkthrough_button, self._essential_walkthrough_button
        )

        buttons.addStretch()
        buttons.addWidget(self._advanced_walkthrough_button)
        buttons.addWidget(self._essential_walkthrough_button)

        layout.addLayout(buttons)

        self.setTabOrder(self._advanced_walkthrough_button, self._essential_walkthrough_button)
        self._essential_walkthrough_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _wire_signals(self) -> None:
        """Connect dialog buttons to their selection handlers."""
        self._advanced_walkthrough_button.clicked.connect(self._on_advanced_walkthrough_clicked)
        self._essential_walkthrough_button.clicked.connect(self._on_essential_walkthrough_clicked)

    def _retranslate_ui(self) -> None:
        """Apply translated text while preserving the current dialog state."""
        self.setWindowTitle(self.tr("Welcome to chappy"))

        self._greeting_label.setText(
            self.tr(
                "chappy guides you through fitting quasar absorption lines,"
                " from raw spectrum to saved analysis."
            )
        )
        self._workflow_label.setText(
            self.tr(
                "The workflow: load observation data, identify absorption"
                " lines, optimize the fit, organize regions and lines, and"
                " correct the continuum when needed before saving your"
                " project."
            )
        )
        if self._sample_available:
            self._sample_intro_label.setText(
                self.tr(
                    "Learn how to use chappy by working with the bundled"
                    " sample (Q0329-385). [Try the Essential Workflow] covers"
                    " loading data, identifying an absorption line, fitting"
                    " it, and saving. [Continue with Advanced Topics] picks up"
                    " from there with custom presets, the velocity plot, region"
                    " editing, cross-ion ties, and continuum correction. Each"
                    " one reloads the sample and runs on its own, so you can"
                    " take them on separate occasions."
                )
            )
        else:
            self._sample_intro_label.setText(
                self.tr(
                    "The bundled sample spectrum was not found in this"
                    " installation. You can still open your own data from"
                    " File > Open Observation Data."
                )
            )

        self._advanced_walkthrough_button.setText(self.tr("Continue with Advanced Topics"))
        self._essential_walkthrough_button.setText(self.tr("Try the Essential Workflow"))

        enforce_translated_minimum_size(
            self, floor=QSize(DialogMetrics.MIN_WIDTH_DEFAULT, DialogMetrics.MIN_HEIGHT_DEFAULT)
        )

    def _on_advanced_walkthrough_clicked(self) -> None:
        """Accept the dialog after recording the advanced walkthrough choice."""
        self._choice = WelcomeDialog.Choice.START_ADVANCED_WALKTHROUGH
        self.accept()

    def _on_essential_walkthrough_clicked(self) -> None:
        """Accept the dialog after recording the essential walkthrough choice."""
        self._choice = WelcomeDialog.Choice.START_ESSENTIAL_WALKTHROUGH
        self.accept()
