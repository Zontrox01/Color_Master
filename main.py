"""
main.py
Punto de entrada de ColorMaster.
"""

import sys

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.theme import DEFAULT_THEME, apply_theme


def _install_spanish_translation(app: QApplication):
    """Carga qtbase_es.qm para traducir los diálogos nativos de Qt
    (QColorDialog, QFileDialog, etc.) al español."""
    translator = QTranslator(app)
    translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load(QLocale("es_ES"), "qtbase", "_", translations_path):
        app.installTranslator(translator)
    else:
        # Algunas instalaciones de PySide6 nombran el archivo sin región.
        translator.load("qtbase_es", translations_path)
        app.installTranslator(translator)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # el estilo nativo de Windows no pinta bien las
                            # flechas de QComboBox/QSpinBox al aplicar QSS;
                            # Fusion es el único estilo de Qt pensado para
                            # funcionar correctamente junto con hojas de estilo.
    _install_spanish_translation(app)
    apply_theme(app, DEFAULT_THEME)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
