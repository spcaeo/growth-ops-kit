"""The Next.js adapter: checks that read a Next.js site's code. Importing this package registers them in gatelib.core.CHECKS.
The gate runs them only when growth.json has "stack": "nextjs"; otherwise it prints "SKIP <id>: no adapter for <stack>"."""
from . import c_cta, c_links, c_page, c_process, c_repo  # noqa: F401
