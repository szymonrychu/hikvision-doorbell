import asyncio
import logging
from functools import wraps
from typing import Any, AsyncGenerator, Callable, Tuple, Type

logger = logging.getLogger(__name__)


def retry_async_yield(
    attempts: int = 3,
    delay: float = 0.0,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
):
    """
    Decorator that turns an async function into an async generator.

    Behavior:
      - On each attempt:
          * If the call raises an exception in `exceptions`: yield None
          * If the call returns None: yield None
          * If the call returns non-None: yield value and stop
      - If all attempts fail and at least one exception was caught:
          * raise the last caught exception
      - If all attempts fail by returning None only:
          * simply stop after yielding None N times
    """

    def decorator(func: Callable[..., Any]):
        @wraps(func)
        async def wrapper(*args, **kwargs) -> AsyncGenerator[Any, None]:
            last_exception = None

            for attempt in range(1, attempts + 1):
                try:
                    result = await func(*args, **kwargs)

                    if result is not None:
                        yield result
                        return  # stop

                except exceptions as exc:
                    last_exception = exc

                # yield None (failed attempt)
                yield None

                # wait if more attempts left
                if attempt < attempts and delay > 0:
                    await asyncio.sleep(delay)

            # If we got here: no success
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def while_async_task_done(
    stop_event: asyncio.Event,
    delay: float = 0.0,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
):
    def decorator(func: Callable[..., Any]):
        @wraps(func)
        async def wrapper(*args, **kwargs) -> AsyncGenerator[Any, None]:
            pass

            while not stop_event.is_set():
                try:
                    result = await func(*args, **kwargs)

                    if result is not None:
                        yield result
                        return  # stop

                except exceptions:
                    pass

                # yield None (failed attempt)
                yield None
                await asyncio.sleep(delay)

        return wrapper

    return decorator
