"""Projects v2 board operations (require a token with the `project` scope).

The board is a *view* over the bridge-managed issues: every Feature and Story
issue becomes a project item carrying Type, Doc, and PMO Project fields. All
mutations are idempotent: re-adding an existing item returns it, and field
writes converge on the same values.
"""
from __future__ import annotations

from .gh import GhRunner

FIELD_SPECS: dict[str, dict] = {
    "Type": {"dataType": "SINGLE_SELECT", "options": ["Feature", "Story"]},
    "Doc": {"dataType": "TEXT"},
    "PMO Project": {"dataType": "TEXT"},
}

_FIELDS_QUERY = """
query($owner: String!, $number: Int!) {
  user(login: $owner) {
    projectV2(number: $number) {
      id
      title
      fields(first: 30) {
        nodes {
          ... on ProjectV2FieldCommon { id name dataType }
          ... on ProjectV2SingleSelectField { id name dataType options { id name } }
        }
      }
    }
  }
}
"""


def create_project(gh: GhRunner, title: str) -> dict:
    viewer = gh.graphql("query { viewer { id login } }")["viewer"]
    data = gh.graphql(
        """
        mutation($owner: ID!, $title: String!) {
          createProjectV2(input: {ownerId: $owner, title: $title}) {
            projectV2 { id number title }
          }
        }
        """,
        owner=viewer["id"], title=title)
    return data["createProjectV2"]["projectV2"]


def get_project(gh: GhRunner, owner: str, number: int) -> dict:
    proj = gh.graphql(_FIELDS_QUERY, owner=owner, number=number)["user"]["projectV2"]
    fields = {}
    for node in proj["fields"]["nodes"]:
        if not node:
            continue
        fields[node["name"]] = {
            "id": node["id"],
            "dataType": node.get("dataType"),
            "options": {o["name"]: o["id"] for o in node.get("options", [])},
        }
    return {"id": proj["id"], "title": proj["title"], "fields": fields}


def ensure_fields(gh: GhRunner, owner: str, number: int) -> dict:
    """Create any missing bridge fields, then return the refreshed project."""
    project = get_project(gh, owner, number)
    for name, spec in FIELD_SPECS.items():
        if name in project["fields"]:
            continue
        if spec["dataType"] == "SINGLE_SELECT":
            opts = ", ".join(
                f'{{name: "{o}", color: GRAY, description: ""}}'
                for o in spec["options"])
            gh.graphql(
                "mutation($p: ID!, $n: String!) { createProjectV2Field(input: {"
                "projectId: $p, dataType: SINGLE_SELECT, name: $n, "
                f"singleSelectOptions: [{opts}]"
                "}) { projectV2Field { ... on ProjectV2FieldCommon { id } } } }",
                p=project["id"], n=name)
        else:
            gh.graphql(
                "mutation($p: ID!, $n: String!) { createProjectV2Field(input: {"
                "projectId: $p, dataType: TEXT, name: $n"
                "}) { projectV2Field { ... on ProjectV2FieldCommon { id } } } }",
                p=project["id"], n=name)
    return get_project(gh, owner, number)


def add_item(gh: GhRunner, project_id: str, content_id: str) -> str:
    data = gh.graphql(
        "mutation($p: ID!, $c: ID!) { addProjectV2ItemById(input: {"
        "projectId: $p, contentId: $c}) { item { id } } }",
        p=project_id, c=content_id)
    return data["addProjectV2ItemById"]["item"]["id"]


def set_text(gh: GhRunner, project_id: str, item_id: str, field_id: str,
             value: str) -> None:
    gh.graphql(
        "mutation($p: ID!, $i: ID!, $f: ID!, $v: String!) {"
        "updateProjectV2ItemFieldValue(input: {projectId: $p, itemId: $i, "
        "fieldId: $f, value: {text: $v}}) { projectV2Item { id } } }",
        p=project_id, i=item_id, f=field_id, v=value)


def set_option(gh: GhRunner, project_id: str, item_id: str, field_id: str,
               option_id: str) -> None:
    gh.graphql(
        "mutation($p: ID!, $i: ID!, $f: ID!, $o: String!) {"
        "updateProjectV2ItemFieldValue(input: {projectId: $p, itemId: $i, "
        "fieldId: $f, value: {singleSelectOptionId: $o}}) "
        "{ projectV2Item { id } } }",
        p=project_id, i=item_id, f=field_id, o=option_id)


def sync_items(gh: GhRunner, project: dict, entries: list[dict]) -> int:
    """entries: [{node_id, doc_id, type ('Feature'|'Story'), pmo_project}]."""
    f = project["fields"]
    type_field, doc_field, pmo_field = f["Type"], f["Doc"], f["PMO Project"]
    for e in entries:
        item = add_item(gh, project["id"], e["node_id"])
        set_option(gh, project["id"], item, type_field["id"],
                   type_field["options"][e["type"]])
        set_text(gh, project["id"], item, doc_field["id"], e["doc_id"])
        set_text(gh, project["id"], item, pmo_field["id"], e["pmo_project"])
    return len(entries)
