"""
Compile call of factory acctording to its type

For each template we expect global variables:
* source - factory.source
* factory_type - factory.type
* provides - factory.provides
* Exit
* NoContextValueError
* UnsupportedFactoryError

When formatting substituted:
* await - "await " for async container or empty string
* async - "async " for async container or empty string
* args - "getter(arg1), getter(arg2)..." or async version
* kwargs - "arg1=getter(arg1), arg2=getter(arg2)..." or async version
* cache - expression to save cache
"""

from .container_objects import CompiledFactory, Exit
from .dependency_source import Factory, FactoryType
from .exceptions import NoContextValueError, UnsupportedFactoryError


def make_args(args: list[str], kwargs: list[str]) -> str:
    res = ", ".join(
        f"{{await}}getter({arg})"
        for arg in args
    )
    if not kwargs:
        return res
    if res:
        res += ", "
    res += ", ".join(
        f"{arg}={{await}}getter({arg})"
        for arg in kwargs
    )
    return res


GENERATOR = """
{async}def get(getter, exits, context):
    generator = source({args})
    solved = next(generator)
    exits.append(Exit(factory_type, generator))
    {cache}
    return solved
"""
ASYNC_GENERATOR = """
{async}def get(getter, exits, context):
    generator = source({args})
    solved = await anext(generator)
    exits.append(Exit(factory_type, generator))
    {cache}
    return solved
"""
FACTORY = """
{async}def get(getter, exits, context):
    solved = source({args})
    {cache}
    return solved
"""
ASYNC_FACTORY = """
{async}def get(getter, exits, context):
    solved = await source({args})
    {cache}
    return solved
"""
VALUE = """
{async}def get(getter, exits, context):
    return source
"""
ALIAS = """
{async}def get(getter, exits, context):
    solved = {args}
    {cache}
    return solved
"""
CONTEXT = """
{async}def get(getter, exits, context):
    raise NoContextValueError(provides.type_hint)
"""
INVALID = """
{async}def get(getter, exits, context):
    raise UnsupportedFactoryError(
        f"Unsupported factory type {{factory_type}}.",
    )
"""

ASYNC_BODIES = {
    FactoryType.ASYNC_FACTORY: ASYNC_FACTORY,
    FactoryType.FACTORY: FACTORY,
    FactoryType.ASYNC_GENERATOR: ASYNC_GENERATOR,
    FactoryType.GENERATOR: GENERATOR,
    FactoryType.VALUE: VALUE,
    FactoryType.CONTEXT: CONTEXT,
    FactoryType.ALIAS: ALIAS,
}
SYNC_BODIES = {
    FactoryType.FACTORY: FACTORY,
    FactoryType.GENERATOR: GENERATOR,
    FactoryType.VALUE: VALUE,
    FactoryType.CONTEXT: CONTEXT,
    FactoryType.ALIAS: ALIAS,
}

CACHE = "context[provides] = solved"


def compile_factory(*, factory: Factory, is_async: bool) -> CompiledFactory:
    args = {
        f"_dishka_arg{i}": dep
        for i, dep in enumerate(factory.dependencies)
    }
    kwargs = factory.kw_dependencies

    if is_async:
        async_ = "async "
        await_ = "await "
        body_template = ASYNC_BODIES.get(factory.type, INVALID)
    else:
        async_ = ""
        await_ = ""
        body_template = SYNC_BODIES.get(factory.type, INVALID)
    if factory.cache:
        cache = CACHE
    else:
        cache = ""

    args_str = make_args(list(args), list(kwargs)).format_map({
        "await": await_,
    })
    body = body_template.format_map({
        "async": async_,
        "await": await_,
        "args": args_str,
        "cache": cache,
    })
    func_globals = {
        "source": factory.source,
        "provides": factory.provides,
        "factory_type": factory.type,
        "Exit": Exit,
        "NoContextValueError": NoContextValueError,
        "UnsupportedFactoryError": UnsupportedFactoryError,
        **args,
        **kwargs,
    }
    exec(body, func_globals)  # noqa: S102
    return func_globals["get"]
