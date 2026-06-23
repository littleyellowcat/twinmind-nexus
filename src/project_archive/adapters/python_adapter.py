"""Python AST extraction for project archives."""

from __future__ import annotations

import ast
import hashlib

from src.project_archive.adapters.base import AdapterExtraction, BaseLanguageAdapter
from src.project_archive.types import EvidenceCard, ProjectEntity, ProjectFile, ProjectRelation


class PythonAdapter(BaseLanguageAdapter):
    language = "python"

    def extract(self, project_file: ProjectFile) -> AdapterExtraction:
        extraction = AdapterExtraction()
        file_entity = ProjectEntity(
            id=project_file.id,
            type="File",
            name=project_file.path,
            source_path=project_file.path,
            properties={"language": project_file.language},
        )
        extraction.entities.append(file_entity)

        try:
            tree = ast.parse(project_file.text)
        except SyntaxError:
            return extraction

        lines = project_file.text.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self._add_definition(extraction, project_file, file_entity, node, "Class", lines)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._add_definition(extraction, project_file, file_entity, node, "Function", lines)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                self._add_import(extraction, project_file, file_entity, node, lines)

        return extraction

    def _add_definition(
        self,
        extraction: AdapterExtraction,
        project_file: ProjectFile,
        file_entity: ProjectEntity,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        entity_type: str,
        lines: list[str],
    ) -> None:
        entity_id = _stable_id(entity_type.lower(), project_file.path, node.name, str(node.lineno))
        evidence_id = _stable_id("ev", project_file.path, node.name, str(node.lineno))
        entity = ProjectEntity(
            id=entity_id,
            type=entity_type,
            name=node.name,
            source_path=project_file.path,
            properties={"language": project_file.language, "line_start": node.lineno},
            evidence_ids=[evidence_id],
        )
        extraction.entities.append(entity)
        extraction.relations.append(
            ProjectRelation(
                id=_stable_id("rel", file_entity.id, entity.id, "DEFINES"),
                source_id=file_entity.id,
                target_id=entity.id,
                type="DEFINES",
                evidence_ids=[evidence_id],
            )
        )
        extraction.evidence_cards.append(
            EvidenceCard(
                id=evidence_id,
                source_type="code",
                source_path=project_file.path,
                title=f"{entity_type}: {node.name}",
                snippet=_snippet(lines, node.lineno, getattr(node, "end_lineno", node.lineno)),
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno),
                linked_entities=[file_entity.id, entity.id],
            )
        )

    def _add_import(
        self,
        extraction: AdapterExtraction,
        project_file: ProjectFile,
        file_entity: ProjectEntity,
        node: ast.Import | ast.ImportFrom,
        lines: list[str],
    ) -> None:
        for name in _import_names(node):
            entity_id = _stable_id("import", name)
            evidence_id = _stable_id("ev", project_file.path, "import", name, str(node.lineno))
            entity = ProjectEntity(
                id=entity_id,
                type="Import",
                name=name,
                source_path=project_file.path,
                evidence_ids=[evidence_id],
            )
            extraction.entities.append(entity)
            extraction.relations.append(
                ProjectRelation(
                    id=_stable_id("rel", file_entity.id, entity.id, "IMPORTS", str(node.lineno)),
                    source_id=file_entity.id,
                    target_id=entity.id,
                    type="IMPORTS",
                    evidence_ids=[evidence_id],
                )
            )
            extraction.evidence_cards.append(
                EvidenceCard(
                    id=evidence_id,
                    source_type="code",
                    source_path=project_file.path,
                    title=f"Import: {name}",
                    snippet=_snippet(lines, node.lineno, getattr(node, "end_lineno", node.lineno)),
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    linked_entities=[file_entity.id, entity.id],
                )
            )


def _import_names(node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]

    module = "." * node.level + (node.module or "")
    return [f"{module}.{alias.name}".strip(".") for alias in node.names]


def _snippet(lines: list[str], line_start: int, line_end: int) -> str:
    return "\n".join(lines[line_start - 1 : line_end])


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1(":".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"
