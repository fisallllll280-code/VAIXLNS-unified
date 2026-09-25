"""VXSL — declarative system language.

VXSL is the source-of-truth language for VAIXLNS system descriptions. It is
intentionally declarative: users describe quantities, equations, states,
constraints, capabilities, minds, simulations, proofs, interfaces and
projects. The compiler lowers VXSL into canonical IR; implementation languages
become targets, not the semantic source of truth.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import re
from typing import Any, Dict, Iterable, List, Mapping, Tuple


@dataclass(frozen=True)
class Quantity:
    name: str
    unit: str
    value: str | None = None


@dataclass(frozen=True)
class Law:
    expression: str
    kind: str = "equation"


@dataclass(frozen=True)
class SystemSpec:
    name: str
    domains: Tuple[str, ...] = ()
    quantities: Tuple[Quantity, ...] = ()
    states: Tuple[str, ...] = ()
    laws: Tuple[Law, ...] = ()
    constraints: Tuple[str, ...] = ()
    capabilities: Tuple[str, ...] = ()
    minds: Tuple[str, ...] = ()
    simulations: Tuple[str, ...] = ()
    proofs: Tuple[str, ...] = ()
    interfaces: Tuple[str, ...] = ()
    project_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class VXSLParser:
    """Minimal line-oriented parser for the first VXSL revision."""

    HEADER = re.compile(r"^system\s+([A-Za-z_][\w-]*)\s*\{$")
    SIMPLE = re.compile(r"^(domain|state|law|constraint|capability|mind|simulate|prove|interface)\s+(.+)$")
    QUANTITY = re.compile(r"^quantity\s+([A-Za-z_][\w-]*)\s*:\s*([A-Za-z0-9_./^-]+)(?:\s*=\s*(.+))?$")
    PROJECT = re.compile(r"^project\s+(.+)$")

    def parse(self, text: str) -> SystemSpec:
        lines=[line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
        if not lines or not self.HEADER.match(lines[0]):
            raise ValueError("VXSL must start with: system Name {")

        name=self.HEADER.match(lines[0]).group(1)  # type: ignore[union-attr]
        domains=[]; quantities=[]; states=[]; laws=[]; constraints=[]
        capabilities=[]; minds=[]; simulations=[]; proofs=[]; interfaces=[]
        project_id=None
        for line in lines[1:]:
            if line == "}":
                continue
            q=self.QUANTITY.match(line)
            if q:
                quantities.append(Quantity(q.group(1),q.group(2),q.group(3)))
                continue
            p=self.PROJECT.match(line)
            if p:
                project_id=p.group(1).strip()
                continue
            m=self.SIMPLE.match(line)
            if not m:
                raise ValueError(f"unrecognized VXSL statement: {line}")
            kind,value=m.groups()
            if kind=="domain": domains.append(value)
            elif kind=="state": states.append(value)
            elif kind=="law": laws.append(Law(value))
            elif kind=="constraint": constraints.append(value)
            elif kind=="capability": capabilities.append(value)
            elif kind=="mind": minds.append(value)
            elif kind=="simulate": simulations.append(value)
            elif kind=="prove": proofs.append(value)
            elif kind=="interface": interfaces.append(value)
        return SystemSpec(
            name=name,
            domains=tuple(dict.fromkeys(domains)),
            quantities=tuple(quantities),
            states=tuple(dict.fromkeys(states)),
            laws=tuple(laws),
            constraints=tuple(dict.fromkeys(constraints)),
            capabilities=tuple(dict.fromkeys(capabilities)),
            minds=tuple(dict.fromkeys(minds)),
            simulations=tuple(dict.fromkeys(simulations)),
            proofs=tuple(dict.fromkeys(proofs)),
            interfaces=tuple(dict.fromkeys(interfaces)),
            project_id=project_id,
        )


def canonical_ir(spec: SystemSpec) -> Dict[str, Any]:
    payload=asdict(spec)
    payload["identity"]="vxs:"+sha256(
        json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
    ).hexdigest()[:20]
    payload["semantics_version"]="1.0"
    payload["source_of_truth"]="VXSL"
    payload["implementation_target_policy"]="polyglot"
    return payload


class VXSLCompiler:
    TARGET_ROLES = {
        "math": ("Python", "Julia", "Lean"),
        "physics": ("Modelica", "FMI", "C++"),
        "engineering": ("Modelica", "FMI", "OpenUSD"),
        "computing": ("Rust", "C++", "Python", "WebAssembly"),
        "data": ("SQL", "Arrow"),
        "ui": ("TypeScript", "WebAssembly"),
    }

    def compile_targets(self, spec: SystemSpec) -> Dict[str, Tuple[str, ...]]:
        roles=[]
        for d in spec.domains:
            roles.extend(self.TARGET_ROLES.get(d, ()))
        return {"targets": tuple(dict.fromkeys(roles))}

    def compile(self, text: str) -> Dict[str, Any]:
        spec=VXSLParser().parse(text)
        ir=canonical_ir(spec)
        ir["compiler"]=self.compile_targets(spec)
        return ir


def round_trip(text: str) -> Dict[str, Any]:
    return VXSLCompiler().compile(text)
