"""Modern internationalization support for Switch conversion notebooks."""

from dataclasses import dataclass
from enum import Enum

from ._base import CaseInsensitiveEnumMixin


class CommentLanguage(CaseInsensitiveEnumMixin, str, Enum):
    """Comment language types for notebook generation"""

    ENGLISH = "English"
    JAPANESE = "Japanese"
    CHINESE = "Chinese"
    FRENCH = "French"
    GERMAN = "German"
    ITALIAN = "Italian"
    KOREAN = "Korean"
    PORTUGUESE = "Portuguese"
    SPANISH = "Spanish"


class MessageKey(Enum):
    """Enum representing all possible message keys used in the application."""

    NOTEBOOK_DESCRIPTION = "notebook_description"
    SOURCE_SCRIPT = "source_script"
    SYNTAX_CHECK_RESULTS = "syntax_check_results"
    ERRORS_FROM_CHECKS = "errors_from_checks"
    PYTHON_SYNTAX_ERRORS = "python_syntax_errors"
    SPARK_SQL_SYNTAX_ERRORS = "spark_sql_syntax_errors"
    NO_ERRORS_DETECTED = "no_errors_detected"
    REVIEW_CODE = "review_code"


@dataclass(frozen=True)
class Messages:
    """Immutable message container for a specific language"""

    notebook_description: str
    source_script: str
    syntax_check_results: str
    errors_from_checks: str
    python_syntax_errors: str
    spark_sql_syntax_errors: str
    no_errors_detected: str
    review_code: str

    def to_dict(self) -> dict[MessageKey, str]:
        """Convert to MessageKey -> str dictionary for backward compatibility"""
        return {
            MessageKey.NOTEBOOK_DESCRIPTION: self.notebook_description,
            MessageKey.SOURCE_SCRIPT: self.source_script,
            MessageKey.SYNTAX_CHECK_RESULTS: self.syntax_check_results,
            MessageKey.ERRORS_FROM_CHECKS: self.errors_from_checks,
            MessageKey.PYTHON_SYNTAX_ERRORS: self.python_syntax_errors,
            MessageKey.SPARK_SQL_SYNTAX_ERRORS: self.spark_sql_syntax_errors,
            MessageKey.NO_ERRORS_DETECTED: self.no_errors_detected,
            MessageKey.REVIEW_CODE: self.review_code,
        }


class MessageManager:
    """Modern, type-safe internationalization manager for Switch"""

    # Language-specific messages defined as class constants
    _LANGUAGE_MESSAGES = {
        CommentLanguage.ENGLISH: Messages(
            notebook_description=(
                "This notebook was automatically converted from the script below. "
                "It may contain errors, so use it as a starting point and make necessary corrections."
            ),
            source_script="Source script",
            syntax_check_results="Static Syntax Check Results",
            errors_from_checks=(
                "These are errors from static syntax checks. Manual corrections are required for these errors."
            ),
            python_syntax_errors="Python Syntax Errors",
            spark_sql_syntax_errors="Spark SQL Syntax Errors",
            no_errors_detected="No syntax errors were detected during the static check.",
            review_code=(
                "However, please review the code carefully as some issues may only be detected during runtime."
            ),
        ),
        CommentLanguage.JAPANESE: Messages(
            notebook_description=(
                "このノートブックは以下のスクリプトから自動的に変換されました。"
                "エラーが含まれている可能性があるため、出発点として使用し、必要な修正を行ってください。"
            ),
            source_script="ソーススクリプト",
            syntax_check_results="静的構文チェック結果",
            errors_from_checks=("以下は静的構文チェックの結果です。エラーがある場合、手動での修正が必要です。"),
            python_syntax_errors="Python構文エラー",
            spark_sql_syntax_errors="Spark SQL構文エラー",
            no_errors_detected="静的チェック中に構文エラーは検出されませんでした。",
            review_code=(
                "ただし、一部の問題は実行時にのみ検出される可能性があるため、" "コードを注意深く確認してください。"
            ),
        ),
        CommentLanguage.CHINESE: Messages(
            notebook_description=("此笔记本是从以下脚本自动转换而来。它可能包含错误，请将其作为起点并进行必要的修正。"),
            source_script="源脚本",
            syntax_check_results="静态语法检查结果",
            errors_from_checks=("这些是静态语法检查中发现的错误。这些错误需要手动修正。"),
            python_syntax_errors="Python语法错误",
            spark_sql_syntax_errors="Spark SQL语法错误",
            no_errors_detected="在静态检查中未检测到语法错误。",
            review_code=("但是，请仔细检查代码，因为某些问题可能只有在运行时才能检测到。"),
        ),
        CommentLanguage.FRENCH: Messages(
            notebook_description=(
                "Ce notebook a été automatiquement converti à partir du script ci-dessous. "
                "Il peut contenir des erreurs, utilisez-le comme point de départ et apportez les corrections nécessaires."
            ),
            source_script="Script source",
            syntax_check_results="Résultats de la vérification syntaxique statique",
            errors_from_checks=(
                "Voici les erreurs détectées lors des vérifications syntaxiques statiques. "
                "Des corrections manuelles sont nécessaires pour ces erreurs."
            ),
            python_syntax_errors="Erreurs de syntaxe Python",
            spark_sql_syntax_errors="Erreurs de syntaxe Spark SQL",
            no_errors_detected="Aucune erreur de syntaxe n'a été détectée lors de la vérification statique.",
            review_code=(
                "Cependant, veuillez examiner attentivement le code car certains problèmes "
                "ne peuvent être détectés que lors de l'exécution."
            ),
        ),
        CommentLanguage.GERMAN: Messages(
            notebook_description=(
                "Dieses Notebook wurde automatisch aus dem unten stehenden Skript konvertiert. "
                "Es kann Fehler enthalten, verwenden Sie es als Ausgangspunkt und nehmen Sie die notwendigen Korrekturen vor."
            ),
            source_script="Quellskript",
            syntax_check_results="Ergebnisse der statischen Syntaxprüfung",
            errors_from_checks=(
                "Dies sind Fehler aus statischen Syntaxprüfungen. "
                "Für diese Fehler sind manuelle Korrekturen erforderlich."
            ),
            python_syntax_errors="Python-Syntaxfehler",
            spark_sql_syntax_errors="Spark SQL-Syntaxfehler",
            no_errors_detected="Bei der statischen Prüfung wurden keine Syntaxfehler festgestellt.",
            review_code=(
                "Überprüfen Sie den Code jedoch sorgfältig, da einige Probleme "
                "möglicherweise erst zur Laufzeit erkannt werden."
            ),
        ),
        CommentLanguage.ITALIAN: Messages(
            notebook_description=(
                "Questo notebook è stato convertito automaticamente dallo script sottostante. "
                "Potrebbe contenere errori, quindi usalo come punto di partenza e apporta le correzioni necessarie."
            ),
            source_script="Script sorgente",
            syntax_check_results="Risultati del controllo sintattico statico",
            errors_from_checks=(
                "Questi sono errori derivanti dai controlli sintattici statici. "
                "Sono necessarie correzioni manuali per questi errori."
            ),
            python_syntax_errors="Errori di sintassi Python",
            spark_sql_syntax_errors="Errori di sintassi Spark SQL",
            no_errors_detected="Non sono stati rilevati errori di sintassi durante il controllo statico.",
            review_code=(
                "Tuttavia, si prega di rivedere attentamente il codice poiché alcuni problemi "
                "potrebbero essere rilevati solo durante l'esecuzione."
            ),
        ),
        CommentLanguage.KOREAN: Messages(
            notebook_description=(
                "이 노트북은 아래 스크립트에서 자동으로 변환되었습니다. "
                "오류가 포함되어 있을 수 있으므로 시작점으로 사용하고 필요한 수정을 하십시오."
            ),
            source_script="소스 스크립트",
            syntax_check_results="정적 구문 검사 결과",
            errors_from_checks=(
                "이것들은 정적 구문 검사에서 발견된 오류입니다. 이러한 오류에는 수동 수정이 필요합니다."
            ),
            python_syntax_errors="Python 구문 오류",
            spark_sql_syntax_errors="Spark SQL 구문 오류",
            no_errors_detected="정적 검사 중 구문 오류가 감지되지 않았습니다.",
            review_code=("그러나 일부 문제는 런타임에만 감지될 수 있으므로 코드를 주의 깊게 검토하십시오."),
        ),
        CommentLanguage.PORTUGUESE: Messages(
            notebook_description=(
                "Este notebook foi convertido automaticamente do script abaixo. "
                "Pode conter erros, então use-o como ponto de partida e faça as correções necessárias."
            ),
            source_script="Script fonte",
            syntax_check_results="Resultados da verificação de sintaxe estática",
            errors_from_checks=(
                "Estes são erros de verificações de sintaxe estática. "
                "Correções manuais são necessárias para esses erros."
            ),
            python_syntax_errors="Erros de sintaxe Python",
            spark_sql_syntax_errors="Erros de sintaxe Spark SQL",
            no_errors_detected="Nenhum erro de sintaxe foi detectado durante a verificação estática.",
            review_code=(
                "No entanto, revise o código cuidadosamente, pois alguns problemas "
                "podem ser detectados apenas durante a execução."
            ),
        ),
        CommentLanguage.SPANISH: Messages(
            notebook_description=(
                "Este notebook se convirtió automáticamente del script a continuación. "
                "Puede contener errores, así que úselo como punto de partida y realice las correcciones necesarias."
            ),
            source_script="Script fuente",
            syntax_check_results="Resultados de la comprobación de sintaxis estática",
            errors_from_checks=(
                "Estos son errores de las comprobaciones de sintaxis estáticas. "
                "Se requieren correcciones manuales para estos errores."
            ),
            python_syntax_errors="Errores de sintaxis de Python",
            spark_sql_syntax_errors="Errores de sintaxis de Spark SQL",
            no_errors_detected="No se detectaron errores de sintaxis durante la comprobación estática.",
            review_code=(
                "Sin embargo, revise cuidadosamente el código, ya que algunos problemas "
                "solo pueden detectarse durante la ejecución."
            ),
        ),
    }

    @classmethod
    def get_message(cls, message_key: MessageKey, language: CommentLanguage = CommentLanguage.ENGLISH) -> str:
        """Get a specific message for the given language

        Args:
            message_key: The message key to retrieve
            language: The language to get the message in

        Returns:
            The localized message string

        Raises:
            KeyError: If the language is not supported
        """
        if language not in cls._LANGUAGE_MESSAGES:
            raise KeyError(f"Unsupported language: {language}")

        messages = cls._LANGUAGE_MESSAGES[language]
        return getattr(messages, message_key.value)

    @classmethod
    def get_all_messages(cls, language: CommentLanguage = CommentLanguage.ENGLISH) -> dict[MessageKey, str]:
        """Get all messages for the specified language

        Args:
            language: The language to get messages for

        Returns:
            Dictionary mapping message keys to localized strings

        Raises:
            KeyError: If the language is not supported
        """
        if language not in cls._LANGUAGE_MESSAGES:
            raise KeyError(f"Unsupported language: {language}")

        return cls._LANGUAGE_MESSAGES[language].to_dict()
