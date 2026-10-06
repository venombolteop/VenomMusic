import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial, wraps

# One pool for the whole process, sized for the work this bot actually does.
# It used to be the default executor, which is small and shared: a queue of
# lookups, several at once, plus anything that blocks on the network filled it
# up, and every later caller waited in silence for a thread that would never
# come free. That showed up as a lookup that simply never returned, with no
# error anywhere.
_POOL = ThreadPoolExecutor(max_workers=32, thread_name_prefix="venom")


def asyncify(func):
    @wraps(func)
    async def run(*args, **kwargs):
        loop = asyncio.get_running_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(_POOL, pfunc)

    return run
