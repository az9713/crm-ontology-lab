"""Strip x-local keys and validate ontology.json against Palantir's own SDK models.
Needs: pip install foundry-platform-sdk   (checked with 1.108.0)
Usage: python check_ontology.py [ontology.json] [extra sys.path entry holding foundry_sdk]"""
import json, sys
from pathlib import Path
if len(sys.argv) > 2: sys.path.insert(0, sys.argv[2])
import pydantic
from foundry_sdk.v2.ontologies import models as m

def strip(x):
    if isinstance(x, dict): return {k: strip(v) for k, v in x.items() if not k.startswith("x-local")}
    if isinstance(x, list): return [strip(v) for v in x]
    return x

def extras(x, path="$"):
    # SDK models use extra="allow", so a misspelled key would pass silently. Report every unknown key.
    if isinstance(x, pydantic.BaseModel):
        for k in (x.__pydantic_extra__ or {}): yield f"{path}.{k}"
        for f in type(x).model_fields: yield from extras(getattr(x, f), f"{path}.{f}")
    elif isinstance(x, dict):
        for k, v in x.items(): yield from extras(v, f"{path}[{k}]")
    elif isinstance(x, list):
        for i, v in enumerate(x): yield from extras(v, f"{path}[{i}]")

src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("ontology.json")
doc = strip(json.loads(src.read_text(encoding="utf-8")))
bad = list(extras(m.OntologyFullMetadata.model_validate(doc)))
assert not bad, "unknown keys:\n" + "\n".join(bad)
print("SDK validation PASS:", len(doc["objectTypes"]), "object types,", len(doc["actionTypes"]), "action types")
