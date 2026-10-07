"""Verified official R4 metadata, bounded datatype expansion and lexical retrieval."""

import hashlib
import io
import json
import re
import tarfile
import urllib.request
from pathlib import Path
from typing import Any

from pydantic import Field

from datapulse.contracts.schema import Contract, NormalizedType

CORE_ID = "hl7.fhir.r4.core"
CORE_VERSION = "4.0.1"
DEFAULT_RESOURCES = ("Patient", "Organization", "Encounter", "Observation", "Provenance")


class CatalogError(Exception):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


class TargetCandidate(Contract):
    id: str
    resource_type: str
    profile_url: str | None = None
    profile_version: str | None = None
    element_path: str
    types: tuple[str, ...]
    min: int = Field(ge=0)
    max: str
    description: str = Field(max_length=1000)
    binding: dict[str, Any] | None = None
    target_profiles: tuple[str, ...] = ()


def package_lock() -> dict[str, Any]:
    return dict(json.loads(Path(__file__).with_name("fhir.lock.json").read_text()))


def cache_package(directory: Path) -> Path:
    lock = package_lock()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{CORE_ID}-{CORE_VERSION}.tgz"
    if path.exists():
        verify_package(path)
        return path
    try:
        with urllib.request.urlopen(lock["url"], timeout=30) as response:
            if response.geturl() != lock["url"]:
                raise CatalogError("unexpected_package_redirect")
            data = response.read(lock["size"] + 1)
        if len(data) != lock["size"] or hashlib.sha256(data).hexdigest() != lock["sha256"]:
            raise CatalogError("package_checksum_mismatch")
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(data)
        temporary.replace(path)
    except OSError:
        raise CatalogError("package_unavailable") from None
    verify_package(path)
    return path


def verify_package(path: Path) -> bytes:
    lock = package_lock()
    try:
        with path.open("rb") as stream:
            data = stream.read(lock["size"] + 1)
    except OSError:
        raise CatalogError("package_unavailable") from None
    if len(data) != lock["size"] or hashlib.sha256(data).hexdigest() != lock["sha256"]:
        raise CatalogError("package_checksum_mismatch")
    return data


def _tokens(text: str) -> set[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def compatible_type(native: NormalizedType, fhir: str) -> bool:
    if fhir == "Reference":
        return native in {"string", "integer", "uuid"}
    choices: dict[str, set[str]] = {
        "string": {"string", "code", "id", "uri", "url", "canonical", "markdown", "base64Binary"},
        "uuid": {"string", "id", "uri"},
        "integer": {"integer", "positiveInt", "unsignedInt", "decimal"},
        "decimal": {"decimal"},
        "boolean": {"boolean"},
        "date": {"date", "dateTime"},
        "datetime": {"dateTime", "instant", "time", "date"},
        "binary": {"base64Binary"},
        "json": set(),
        "unknown": set(),
    }
    # String dates, flags, codes and references require a declared transformation,
    # but must be retrievable for proposal/review rather than silently discarded.
    if native == "string" and fhir in {"date", "dateTime", "instant", "boolean", "Reference"}:
        return True
    return fhir in choices[native]


class FHIRCatalog:
    def __init__(
        self,
        definitions: dict[str, dict[str, Any]],
        digest: str,
        terminology: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._definitions = definitions
        self.digest = digest
        self._candidates: dict[str, tuple[TargetCandidate, ...]] = {}
        self._terminology = terminology or {}

    @classmethod
    def load(cls, path: Path) -> "FHIRCatalog":
        data = verify_package(path)
        definitions: dict[str, dict[str, Any]] = {}
        terminology: dict[str, dict[str, Any]] = {}
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
                members = archive.getmembers()
                if len(members) > 6000:
                    raise CatalogError("invalid_package")
                manifest_file = archive.extractfile("package/package.json")
                if manifest_file is None:
                    raise CatalogError("invalid_package")
                manifest = json.load(manifest_file)
                if (
                    manifest["name"] != CORE_ID
                    or manifest["version"] != CORE_VERSION
                    or manifest.get("dependencies", {}) != package_lock()["dependencies"]
                    or manifest.get("fhirVersions") != [CORE_VERSION]
                ):
                    raise CatalogError("package_manifest_mismatch")
                for member in members:
                    if re.fullmatch(r"package/(ValueSet|CodeSystem)-[^/]+\.json", member.name):
                        if not member.isfile() or member.size > 4000000:
                            raise CatalogError("invalid_package")
                        stream = archive.extractfile(member)
                        if stream is None:
                            raise CatalogError("invalid_package")
                        item = json.load(stream)
                        terminology[item["url"]] = item
                        continue
                    if not re.fullmatch(r"package/StructureDefinition-[^/]+\.json", member.name):
                        continue
                    if not member.isfile() or member.size > 4000000:
                        raise CatalogError("invalid_package")
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise CatalogError("invalid_package")
                    definition = json.load(stream)
                    if definition.get("derivation") == "specialization":
                        definitions[definition["type"]] = definition
        except (tarfile.TarError, ValueError, KeyError):
            raise CatalogError("invalid_package") from None
        if not set(DEFAULT_RESOURCES) <= set(definitions):
            raise CatalogError("missing_core_definitions")
        return cls(definitions, package_lock()["sha256"], terminology)

    def binding_codes(self, canonical: str) -> set[str] | None:
        url, _, version = canonical.partition("|")
        item = self._terminology.get(url)
        if item is None or (version and item.get("version") != version):
            return None
        if item.get("resourceType") == "CodeSystem":
            return None
        compose = item.get("compose", {})
        if compose.get("exclude"):
            return None
        allowed: set[str] = set()
        for include in compose.get("include", []):
            if include.get("filter") or include.get("valueSet"):
                return None
            if include.get("concept"):
                allowed.update(c["code"] for c in include["concept"])
            else:
                system = self._terminology.get(include.get("system", ""))
                if system is None or system.get("content") != "complete":
                    return None
                if include.get("version") and include["version"] != system.get("version"):
                    return None

                def codes(concepts: list[dict[str, Any]], depth: int = 0) -> None:
                    if depth > 12:
                        raise CatalogError("terminology_depth_limit")
                    for concept in concepts:
                        allowed.add(concept["code"])
                        codes(concept.get("concept", []), depth + 1)

                codes(system.get("concept", []))
        return allowed or None

    def candidates(self, resource: str) -> tuple[TargetCandidate, ...]:
        if resource not in self._candidates:
            root = self._definitions.get(resource)
            if root is None or root.get("kind") != "resource":
                raise CatalogError("resource_unavailable")
            result: dict[str, TargetCandidate] = {}

            def expand(
                kind: str,
                prefix: str,
                depth: int,
                ancestors: tuple[str, ...],
                inherited_binding: dict[str, Any] | None = None,
            ) -> None:
                if depth > 4 or kind in ancestors:
                    return
                definition = self._definitions.get(kind)
                if definition is None:
                    return
                elements = definition.get("snapshot", {}).get("element", [])
                for element in elements[1:]:
                    relative = element["path"].split(".", 1)[1]
                    # Nested BackboneElement children occur in the resource snapshot.
                    # Resolve ancestor array/choice names from those same definitions.
                    segments = relative.split(".")
                    path_parts = []
                    for number, segment in enumerate(segments):
                        ancestor_path = kind + "." + ".".join(segments[: number + 1])
                        ancestor = next(
                            (e for e in elements if e["path"] == ancestor_path), element
                        )
                        suffix = "[]" if ancestor.get("max") not in {"0", "1"} else ""
                        path_parts.append(segment + suffix)
                    base_path = prefix + ".".join(path_parts)
                    if element.get("max") == "0" or element.get("contentReference"):
                        continue
                    for datatype in element.get("type", []):
                        code = datatype["code"]
                        if code.startswith("http://hl7.org/fhirpath/System."):
                            continue
                        path = base_path.replace("[x]", code[0].upper() + code[1:])
                        native_def = self._definitions.get(code, {})
                        is_leaf = native_def.get("kind") == "primitive-type" or code == "Reference"
                        if is_leaf:
                            identity = f"{self.digest}:{resource}:{path}:{code}"
                            result[path] = TargetCandidate(
                                id=hashlib.sha256(identity.encode()).hexdigest(),
                                resource_type=resource,
                                profile_url=root["url"],
                                profile_version=CORE_VERSION,
                                element_path=path,
                                types=(code,),
                                min=element.get("min", 0),
                                max=element.get("max", "1"),
                                description=str(element.get("short", ""))[:1000],
                                binding=element.get("binding")
                                or (inherited_binding if code == "code" else None),
                                target_profiles=tuple(datatype.get("targetProfile", [])),
                            )
                        elif code not in {"Element", "BackboneElement", "Extension"}:
                            expand(
                                code,
                                path + ".",
                                depth + 1,
                                (*ancestors, kind),
                                element.get("binding") or inherited_binding,
                            )
                        if len(result) > 10000:
                            raise CatalogError("catalog_expansion_limit")

            expand(resource, "", 0, ())
            self._candidates[resource] = tuple(result[path] for path in sorted(result))
        return self._candidates[resource]

    def required_elements(self, resource: str) -> tuple[str, ...]:
        definition = self._definitions.get(resource)
        if definition is None:
            raise CatalogError("resource_unavailable")
        return tuple(
            e["path"].split(".", 1)[1]
            for e in definition.get("snapshot", {}).get("element", [])
            if e["path"].count(".") == 1 and e.get("min", 0) > 0
        )

    def retrieve(
        self,
        field_name: str,
        native_type: NormalizedType,
        resources: tuple[str, ...] = DEFAULT_RESOURCES,
        limit: int = 12,
    ) -> tuple[TargetCandidate, ...]:
        if not 1 <= limit <= 12 or len(resources) > 8:
            raise CatalogError("retrieval_limit")
        words = _tokens(field_name)
        aliases = {
            "dob": {"birth", "date"},
            "birthdate": {"birth", "date"},
            "sex": {"gender"},
            "pat": {"patient"},
            "fname": {"given"},
            "lname": {"family"},
            "pid": {"identifier"},
        }
        for word in tuple(words):
            words.update(aliases.get(word, set()))
        scored = []
        for resource in resources:
            for candidate in self.candidates(resource):
                if not any(compatible_type(native_type, t) for t in candidate.types):
                    continue
                path_words = _tokens(candidate.element_path)
                score = 3 * len(words & path_words) + len(words & _tokens(candidate.description))
                score += 8 * len(words & _tokens(candidate.element_path.rsplit(".", 1)[-1]))
                score -= candidate.element_path.count(".")
                if score:
                    scored.append((score, candidate))
        scored.sort(key=lambda item: (-item[0], item[1].resource_type, item[1].element_path))
        return tuple(candidate for _, candidate in scored[:limit])
