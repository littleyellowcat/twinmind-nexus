"""Tree-sitter extraction for multi-language project archives."""

from __future__ import annotations

import hashlib
import importlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from src.project_archive.adapters.base import AdapterExtraction, BaseLanguageAdapter
from src.project_archive.types import EvidenceCard, ProjectEntity, ProjectFile, ProjectRelation

try:  # pragma: no cover - exercised when optional dependency is installed.
    from tree_sitter import Language, Node, Parser
except ImportError:  # pragma: no cover - lets archive ingestion degrade gracefully.
    Language = None  # type: ignore[assignment]
    Node = Any  # type: ignore[misc, assignment]
    Parser = None  # type: ignore[assignment]


LANGUAGE_LOADERS = {
    "java": ("tree_sitter_java", "language"),
    "cpp": ("tree_sitter_cpp", "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "tsx": ("tree_sitter_typescript", "language_tsx"),
    "javascript": ("tree_sitter_javascript", "language"),
    "go": ("tree_sitter_go", "language"),
    "rust": ("tree_sitter_rust", "language"),
}

STRUCTURE_NODE_TYPES = {
    "class_declaration": "Class",
    "class_specifier": "Class",
    "interface_declaration": "Interface",
    "enum_declaration": "Enum",
    "enum_item": "Enum",
    "struct_specifier": "Struct",
    "struct_item": "Struct",
    "type_alias_declaration": "TypeAlias",
    "type_declaration": "Type",
    "trait_item": "Trait",
    "impl_item": "Implementation",
    "function_declaration": "Function",
    "function_definition": "Function",
    "function_item": "Function",
    "function_signature_item": "Function",
    "method_declaration": "Method",
    "method_definition": "Method",
    "constructor_declaration": "Method",
    "lexical_declaration": "Function",
    "mod_item": "Module",
    "namespace_definition": "Namespace",
}

IMPORT_NODE_TYPES = {
    "import_declaration",
    "import_statement",
    "preproc_include",
    "import_declaration",
    "use_declaration",
}

PACKAGE_NODE_TYPES = {"package_declaration", "package_clause"}
CALL_NODE_TYPES = {"call_expression", "method_invocation"}


@dataclass(frozen=True)
class _Definition:
    id: str
    name: str
    type: str
    node: Node


class TreeSitterCodeAdapter(BaseLanguageAdapter):
    """Extract code entities and relations from Tree-sitter syntax trees."""

    def __init__(self, language: str) -> None:
        self.language = language
        self._parser = _parser_for_language(language)

    def extract(self, project_file: ProjectFile) -> AdapterExtraction:
        file_entity = ProjectEntity(
            id=project_file.id,
            type="File",
            name=project_file.path,
            source_path=project_file.path,
            properties={"language": project_file.language},
        )
        extraction = AdapterExtraction(entities=[file_entity])
        if self._parser is None:
            return extraction

        source_bytes = project_file.text.encode("utf-8", errors="replace")
        tree = self._parser.parse(source_bytes)
        lines = project_file.text.splitlines()
        definitions: list[_Definition] = []

        for node in _walk(tree.root_node):
            if node.type in PACKAGE_NODE_TYPES:
                self._add_package(extraction, project_file, file_entity, node, source_bytes, lines)
            elif node.type in IMPORT_NODE_TYPES:
                self._add_import(extraction, project_file, file_entity, node, source_bytes, lines)
            elif node.type in STRUCTURE_NODE_TYPES:
                definition = self._add_definition(
                    extraction,
                    project_file,
                    file_entity,
                    node,
                    source_bytes,
                    lines,
                    definitions,
                )
                if definition is not None:
                    definitions.append(definition)

        for node in _walk(tree.root_node):
            if node.type in CALL_NODE_TYPES:
                self._add_call(
                    extraction,
                    project_file,
                    node,
                    source_bytes,
                    lines,
                    definitions,
                )

        return extraction

    def _add_package(
        self,
        extraction: AdapterExtraction,
        project_file: ProjectFile,
        file_entity: ProjectEntity,
        node: Node,
        source_bytes: bytes,
        lines: list[str],
    ) -> None:
        name = _package_name(node, source_bytes)
        if not name:
            return
        entity_id = _stable_id("package", project_file.language, name)
        evidence_id = _stable_id("ev", project_file.path, "package", name, str(_line_start(node)))
        entity = ProjectEntity(
            id=entity_id,
            type="Package",
            name=name,
            source_path=project_file.path,
            properties={"language": project_file.language},
            evidence_ids=[evidence_id],
        )
        extraction.entities.append(entity)
        extraction.relations.append(
            ProjectRelation(
                id=_stable_id("rel", file_entity.id, entity.id, "DECLARES_PACKAGE"),
                source_id=file_entity.id,
                target_id=entity.id,
                type="DECLARES_PACKAGE",
                evidence_ids=[evidence_id],
            )
        )
        extraction.evidence_cards.append(
            _evidence(project_file, evidence_id, f"Package: {name}", node, lines, [file_entity.id, entity.id])
        )

    def _add_import(
        self,
        extraction: AdapterExtraction,
        project_file: ProjectFile,
        file_entity: ProjectEntity,
        node: Node,
        source_bytes: bytes,
        lines: list[str],
    ) -> None:
        name = _import_name(node, source_bytes)
        if not name:
            return
        entity_id = _stable_id("import", project_file.language, name)
        dependency_id = _stable_id("dependency", _dependency_root(name))
        evidence_id = _stable_id("ev", project_file.path, "import", name, str(_line_start(node)))
        import_entity = ProjectEntity(
            id=entity_id,
            type="Import",
            name=name,
            source_path=project_file.path,
            properties={"language": project_file.language},
            evidence_ids=[evidence_id],
        )
        dependency_entity = ProjectEntity(
            id=dependency_id,
            type="Dependency",
            name=_dependency_root(name),
            source_path=project_file.path,
            properties={"language": project_file.language, "import": name},
            evidence_ids=[evidence_id],
        )
        extraction.entities.extend([import_entity, dependency_entity])
        extraction.relations.extend(
            [
                ProjectRelation(
                    id=_stable_id("rel", file_entity.id, import_entity.id, "IMPORTS", str(_line_start(node))),
                    source_id=file_entity.id,
                    target_id=import_entity.id,
                    type="IMPORTS",
                    evidence_ids=[evidence_id],
                ),
                ProjectRelation(
                    id=_stable_id("rel", file_entity.id, dependency_entity.id, "DEPENDS_ON", str(_line_start(node))),
                    source_id=file_entity.id,
                    target_id=dependency_entity.id,
                    type="DEPENDS_ON",
                    evidence_ids=[evidence_id],
                ),
            ]
        )
        extraction.evidence_cards.append(
            _evidence(project_file, evidence_id, f"Import: {name}", node, lines, [file_entity.id, import_entity.id, dependency_entity.id])
        )

    def _add_definition(
        self,
        extraction: AdapterExtraction,
        project_file: ProjectFile,
        file_entity: ProjectEntity,
        node: Node,
        source_bytes: bytes,
        lines: list[str],
        definitions: list[_Definition],
    ) -> _Definition | None:
        name = _definition_name(node, source_bytes)
        if not name or name in {"const", "let", "var"}:
            return None
        entity_type = _definition_type(node, source_bytes)
        evidence_id = _stable_id("ev", project_file.path, entity_type, name, str(_line_start(node)))
        entity_id = _stable_id(
            entity_type.lower(),
            project_file.path,
            name,
            str(_line_start(node)),
        )
        properties = {
            "language": project_file.language,
            "line_start": _line_start(node),
            "line_end": _line_end(node),
        }
        roles = _semantic_roles(name, entity_type, project_file.path)
        if roles:
            properties["semantic_roles"] = roles
        entity = ProjectEntity(
            id=entity_id,
            type=entity_type,
            name=name,
            source_path=project_file.path,
            properties=properties,
            evidence_ids=[evidence_id],
        )
        extraction.entities.append(entity)
        parent_definition = _nearest_definition(definitions, node)
        source_id = parent_definition.id if parent_definition else file_entity.id
        relation_type = "DEFINES"
        extraction.relations.append(
            ProjectRelation(
                id=_stable_id("rel", source_id, entity.id, relation_type, str(_line_start(node))),
                source_id=source_id,
                target_id=entity.id,
                type=relation_type,
                evidence_ids=[evidence_id],
            )
        )
        for relation_type, target_name in _type_relations(node, source_bytes):
            target_id = _stable_id("external_type", target_name)
            target = ProjectEntity(
                id=target_id,
                type="ExternalType",
                name=target_name,
                source_path=project_file.path,
                properties={"language": project_file.language},
                evidence_ids=[evidence_id],
            )
            extraction.entities.append(target)
            extraction.relations.append(
                ProjectRelation(
                    id=_stable_id("rel", entity.id, target_id, relation_type, str(_line_start(node))),
                    source_id=entity.id,
                    target_id=target_id,
                    type=relation_type,
                    evidence_ids=[evidence_id],
                )
            )
        extraction.evidence_cards.append(
            _evidence(project_file, evidence_id, f"{entity_type}: {name}", node, lines, [file_entity.id, entity.id])
        )
        return _Definition(id=entity_id, name=name, type=entity_type, node=node)

    def _add_call(
        self,
        extraction: AdapterExtraction,
        project_file: ProjectFile,
        node: Node,
        source_bytes: bytes,
        lines: list[str],
        definitions: list[_Definition],
    ) -> None:
        caller = _nearest_definition(definitions, node)
        if caller is None:
            return
        call_name = _call_name(node, source_bytes)
        if not call_name or call_name in {caller.name, "return"}:
            return
        evidence_id = _stable_id("ev", project_file.path, "call", call_name, str(_line_start(node)))
        call_id = _stable_id("call", project_file.path, call_name, str(_line_start(node)))
        call_entity = ProjectEntity(
            id=call_id,
            type="Call",
            name=call_name,
            source_path=project_file.path,
            properties={"language": project_file.language, "line_start": _line_start(node)},
            evidence_ids=[evidence_id],
        )
        extraction.entities.append(call_entity)
        extraction.relations.append(
            ProjectRelation(
                id=_stable_id("rel", caller.id, call_id, "CALLS", str(_line_start(node))),
                source_id=caller.id,
                target_id=call_id,
                type="CALLS",
                evidence_ids=[evidence_id],
            )
        )
        extraction.evidence_cards.append(
            _evidence(project_file, evidence_id, f"Call: {call_name}", node, lines, [caller.id, call_id])
        )


def _parser_for_language(language: str) -> Parser | None:
    if Parser is None or Language is None:
        return None
    loader_key = "tsx" if language == "typescript_tsx" else language
    module_name, function_name = LANGUAGE_LOADERS.get(loader_key, ("", ""))
    if not module_name:
        return None
    try:
        module = importlib.import_module(module_name)
        language_capsule = getattr(module, function_name)()
        return Parser(Language(language_capsule))
    except Exception:
        return None


def _walk(node: Node) -> Iterable[Node]:
    yield node
    for child in node.children:
        if child.is_named:
            yield from _walk(child)


def _text(node: Node | None, source_bytes: bytes) -> str:
    if node is None:
        return ""
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore").strip()


def _line_start(node: Node) -> int:
    return int(node.start_point[0]) + 1


def _line_end(node: Node) -> int:
    return int(node.end_point[0]) + 1


def _field(node: Node, name: str) -> Node | None:
    try:
        return node.child_by_field_name(name)
    except Exception:
        return None


def _named_children(node: Node, *types: str) -> list[Node]:
    wanted = set(types)
    return [child for child in node.children if child.is_named and child.type in wanted]


def _package_name(node: Node, source_bytes: bytes) -> str:
    identifiers = [
        _text(child, source_bytes)
        for child in _walk(node)
        if child.type in {"identifier", "package_identifier", "scoped_identifier"}
    ]
    return ".".join(part for part in identifiers if part) if node.type == "package_clause" else (identifiers[-1] if identifiers else "")


def _import_name(node: Node, source_bytes: bytes) -> str:
    path_node = (
        _field(node, "path")
        or _field(node, "source")
        or _field(node, "argument")
        or _first_field_descendant(node, "path")
        or _first_field_descendant(node, "source")
        or _first_field_descendant(node, "argument")
    )
    if path_node is not None:
        return _clean_import_text(_text(path_node, source_bytes))
    if node.type == "import_declaration":
        parts = [
            _text(child, source_bytes)
            for child in _walk(node)
            if child.type in {"scoped_identifier", "identifier", "asterisk"}
        ]
        return parts[0] if parts else ""
    return _clean_import_text(_text(node, source_bytes))


def _clean_import_text(value: str) -> str:
    text = value.strip().strip(";").strip()
    for prefix in ("import ", "use ", "#include "):
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
    if " from " in text:
        text = text.rsplit(" from ", 1)[-1].strip()
    return text.strip("\"'<>;")


def _definition_name(node: Node, source_bytes: bytes) -> str:
    name_node = _field(node, "name")
    if name_node is not None:
        return _text(name_node, source_bytes)
    if node.type == "type_declaration":
        type_spec = next(iter(_named_children(node, "type_spec")), None)
        spec_name = _field(type_spec, "name") if type_spec is not None else None
        if spec_name is not None:
            return _text(spec_name, source_bytes)
    declarator = _field(node, "declarator")
    if declarator is not None:
        nested_name = _first_named_descendant(
            declarator,
            {"field_identifier", "identifier", "qualified_identifier"},
        )
        if nested_name is not None:
            return _text(nested_name, source_bytes).split("::")[-1]
    if node.type == "lexical_declaration":
        declarators = _named_children(node, "variable_declarator")
        for declarator in declarators:
            value = _field(declarator, "value")
            if value is not None and value.type == "arrow_function":
                return _text(_field(declarator, "name"), source_bytes)
        return ""
    if node.type == "impl_item":
        type_node = _field(node, "type")
        return f"impl {_text(type_node, source_bytes)}".strip()
    return ""


def _definition_type(node: Node, source_bytes: bytes) -> str:
    if node.type == "type_declaration":
        type_spec = next(iter(_named_children(node, "type_spec")), None)
        type_node = _field(type_spec, "type") if type_spec is not None else None
        if type_node is not None and type_node.type == "struct_type":
            return "Struct"
        if type_node is not None and type_node.type == "interface_type":
            return "Interface"
    if node.type == "lexical_declaration":
        return "Function"
    if node.type == "impl_item":
        return "Implementation"
    return STRUCTURE_NODE_TYPES[node.type]


def _first_named_descendant(node: Node, types: set[str]) -> Node | None:
    for child in _walk(node):
        if child.type in types:
            return child
    return None


def _first_field_descendant(node: Node, field_name: str) -> Node | None:
    for child in _walk(node):
        found = _field(child, field_name)
        if found is not None:
            return found
    return None


def _type_relations(node: Node, source_bytes: bytes) -> list[tuple[str, str]]:
    relations: list[tuple[str, str]] = []
    superclass = _field(node, "superclass")
    if superclass is not None:
        name = _last_type_identifier(superclass, source_bytes)
        if name:
            relations.append(("EXTENDS", name))
    interfaces = _field(node, "interfaces")
    if interfaces is not None:
        for name in _all_type_identifiers(interfaces, source_bytes):
            relations.append(("IMPLEMENTS", name))
    return relations


def _last_type_identifier(node: Node, source_bytes: bytes) -> str:
    names = _all_type_identifiers(node, source_bytes)
    return names[-1] if names else ""


def _all_type_identifiers(node: Node, source_bytes: bytes) -> list[str]:
    return [
        _text(child, source_bytes)
        for child in _walk(node)
        if child.type in {"type_identifier", "identifier", "qualified_type_identifier"}
    ]


def _call_name(node: Node, source_bytes: bytes) -> str:
    function_node = _field(node, "function") or _field(node, "name")
    if function_node is None:
        children = [child for child in node.children if child.is_named]
        function_node = children[0] if children else None
    name = _text(function_node, source_bytes)
    return name.split("(")[0].strip()


def _nearest_definition(definitions: list[_Definition], node: Node) -> _Definition | None:
    candidates = [
        definition
        for definition in definitions
        if definition.node.start_byte <= node.start_byte
        and definition.node.end_byte >= node.end_byte
        and definition.node.id != node.id
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.node.end_byte - item.node.start_byte)[0]


def _semantic_roles(name: str, entity_type: str, source_path: str) -> list[str]:
    text = f"{name} {entity_type} {source_path}".lower()
    roles = []
    role_keywords = {
        "service_boundary": ("service", "controller", "handler", "router", "endpoint"),
        "data_boundary": ("repository", "dao", "storage", "database", "model"),
        "rag_component": ("rag", "retriev", "vector", "embedding", "rerank", "llm", "agent"),
    }
    for role, keywords in role_keywords.items():
        if any(keyword in text for keyword in keywords):
            roles.append(role)
    if name.lower() == "main":
        roles.append("entry_point")
    return roles


def _dependency_root(name: str) -> str:
    cleaned = name.strip().strip("\"'<>")
    if cleaned.startswith("@") and "/" in cleaned:
        return "/".join(cleaned.split("/")[:2])
    separators = ["::", ".", "/"]
    for separator in separators:
        if separator in cleaned:
            return cleaned.split(separator, 1)[0]
    return cleaned


def _evidence(
    project_file: ProjectFile,
    evidence_id: str,
    title: str,
    node: Node,
    lines: list[str],
    linked_entities: list[str],
) -> EvidenceCard:
    return EvidenceCard(
        id=evidence_id,
        source_type="code",
        source_path=project_file.path,
        title=title,
        snippet=_snippet(lines, _line_start(node), _line_end(node)),
        line_start=_line_start(node),
        line_end=_line_end(node),
        linked_entities=linked_entities,
    )


def _snippet(lines: list[str], line_start: int, line_end: int) -> str:
    if not lines:
        return ""
    safe_start = max(1, line_start)
    safe_end = min(len(lines), line_end)
    return "\n".join(lines[safe_start - 1 : safe_end])[:1200]


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1(":".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"
