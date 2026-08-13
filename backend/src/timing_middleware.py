
import time
from fastapi import Request
from src.llm_shim import tu

async def request_timing_middleware(request: Request, call_next):
    """
    Middleware to log total request processing time.
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Format process_time to 4 decimal places
    process_time_str = f"{process_time:.4f}"
    
    # Log the timing using print to match user's requested style or logging
    # tu.logger.info(f"Total Request Processing Time: {process_time_str}s")
    print(f"Total Request Processing Time: {process_time_str}s")
    
    # Add header to response
    response.headers["X-Process-Time"] = process_time_str
    
    return response

async def measure_middleware_timing(middleware_name: str, request: Request, call_next):
    """
    Helper wrapper to measure execution time of a specific middleware.
    """
    start = time.time()
    try:
        response = await call_next(request)
        return response
    finally:
        end = time.time()
        print(f"[{middleware_name}] Execution time: {end - start:.4f}s")

