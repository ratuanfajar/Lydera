SECTION_ORDER = ("ROLE", "TASK", "CONTEXT", "RULES", "OUTPUT FORMAT", "EXAMPLES")


def build_prompt(*, role, task, context=None, rules=None, output_format=None, examples=None) -> str:
    bodies = {
        "ROLE": role,
        "TASK": task,
        "CONTEXT": context,
        "RULES": rules,
        "OUTPUT FORMAT": output_format,
        "EXAMPLES": examples,
    }
    return "\n\n".join(_section(name, bodies[name]) for name in SECTION_ORDER if bodies[name])


def build_input(**sections) -> str:
    return "\n\n".join(_section(name.replace("_", " ").upper(), body) for name, body in sections.items() if body)


def _section(name: str, body) -> str:
    return f"# {name}\n{_render(body)}"


def _render(body) -> str:
    if isinstance(body, str):
        return body.strip()
    return "\n".join(f"- {item.strip()}" for item in body)
