"""Evolution endpoints for self-evolving code."""

import asyncio
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from api.middleware.auth import verify_api_key
from api.models import EvolveRequest, EvolveResponse, EvolveStatusResponse, TaskStatus
from config import get_logger
from core.claude_client import claude_client

logger = get_logger(__name__)

router = APIRouter(prefix="/evolve", tags=["evolve"])

# In-memory task storage (use Redis/DB in production)
_tasks: dict[str, dict[str, Any]] = {}


async def run_evolution(task_id: str, request: EvolveRequest) -> None:
    """
    Run the evolution loop in the background.

    This is the core self-evolving code logic:
    1. Analyze current code
    2. Generate improvements
    3. Apply changes
    4. Run tests
    5. Evaluate results
    6. Repeat or finish
    """
    task = _tasks[task_id]
    task["status"] = TaskStatus.RUNNING
    task["started_at"] = datetime.utcnow()

    try:
        for iteration in range(1, request.max_iterations + 1):
            task["current_iteration"] = iteration
            logger.info(
                "evolution_iteration",
                task_id=task_id,
                iteration=iteration,
                max=request.max_iterations,
            )

            # Step 1: Analyze
            analyze_prompt = f"""Analyze the code at '{request.target_path}' for improvements.

Objective: {request.objective}
Constraints: {', '.join(request.constraints) if request.constraints else 'None'}

Current iteration: {iteration}/{request.max_iterations}

Please:
1. Read and analyze the current code
2. Identify specific improvements aligned with the objective
3. Explain what changes you will make and why"""

            analyze_response = await claude_client.query(
                prompt=analyze_prompt,
                allowed_tools=["Read", "Glob", "Grep"],
                max_turns=5,
            )

            task["changes"].append({
                "iteration": iteration,
                "phase": "analyze",
                "result": analyze_response.result,
                "timestamp": datetime.utcnow().isoformat(),
            })

            # Step 2: Implement
            implement_prompt = f"""Based on your analysis, now implement the improvements.

Objective: {request.objective}

Make the necessary changes to the code. Be precise and only make changes that align with the objective."""

            implement_response = await claude_client.query(
                prompt=implement_prompt,
                session_id=analyze_response.session_id,
                allowed_tools=["Read", "Edit", "Write"],
                max_turns=10,
            )

            task["changes"].append({
                "iteration": iteration,
                "phase": "implement",
                "result": implement_response.result,
                "tools_used": implement_response.tools_used,
                "timestamp": datetime.utcnow().isoformat(),
            })

            # Step 3: Test (if test command provided)
            if request.test_command:
                test_prompt = f"""Run the tests to verify the changes work correctly.

Test command: {request.test_command}

Execute the tests and report the results."""

                test_response = await claude_client.query(
                    prompt=test_prompt,
                    session_id=implement_response.session_id,
                    allowed_tools=["Bash"],
                    max_turns=3,
                )

                task["test_results"].append({
                    "iteration": iteration,
                    "result": test_response.result,
                    "timestamp": datetime.utcnow().isoformat(),
                })

                # Check if tests passed
                if "FAILED" in test_response.result.upper() or "ERROR" in test_response.result.upper():
                    # Rollback or fix
                    logger.warning("evolution_tests_failed", task_id=task_id, iteration=iteration)

                    fix_prompt = """The tests failed. Please analyze the failures and fix the issues."""

                    fix_response = await claude_client.query(
                        prompt=fix_prompt,
                        session_id=test_response.session_id,
                        allowed_tools=["Read", "Edit", "Bash"],
                        max_turns=10,
                    )

                    task["changes"].append({
                        "iteration": iteration,
                        "phase": "fix",
                        "result": fix_response.result,
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            # Step 4: Evaluate
            evaluate_prompt = f"""Evaluate the current state of the code against the objective.

Objective: {request.objective}

Rate the progress on a scale of 1-10 and explain:
1. What has been achieved
2. What still needs improvement
3. Whether we should continue iterating or if the objective is met

If the objective is fully met, say "OBJECTIVE_COMPLETE" at the end."""

            evaluate_response = await claude_client.query(
                prompt=evaluate_prompt,
                session_id=implement_response.session_id if not request.test_command else test_response.session_id,
                allowed_tools=["Read"],
                max_turns=3,
            )

            task["changes"].append({
                "iteration": iteration,
                "phase": "evaluate",
                "result": evaluate_response.result,
                "timestamp": datetime.utcnow().isoformat(),
            })

            # Check if objective is complete
            if "OBJECTIVE_COMPLETE" in evaluate_response.result:
                logger.info("evolution_objective_complete", task_id=task_id, iteration=iteration)
                break

            # Small delay between iterations
            await asyncio.sleep(1)

        task["status"] = TaskStatus.COMPLETED
        task["completed_at"] = datetime.utcnow()
        logger.info("evolution_completed", task_id=task_id)

    except Exception as e:
        logger.exception("evolution_failed", task_id=task_id, error=str(e))
        task["status"] = TaskStatus.FAILED
        task["error"] = str(e)
        task["completed_at"] = datetime.utcnow()


@router.post("/iterate", response_model=EvolveResponse)
async def start_evolution(
    request: EvolveRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_api_key),
) -> EvolveResponse:
    """
    Start a code evolution task.

    This runs the full evolution cycle in the background:
    Analyze → Implement → Test → Evaluate → Repeat
    """
    task_id = str(uuid.uuid4())

    # Initialize task
    _tasks[task_id] = {
        "status": TaskStatus.PENDING,
        "current_iteration": 0,
        "max_iterations": request.max_iterations,
        "objective": request.objective,
        "target_path": request.target_path,
        "changes": [],
        "test_results": [],
        "error": None,
        "started_at": None,
        "completed_at": None,
    }

    # Run in background
    background_tasks.add_task(run_evolution, task_id, request)

    return EvolveResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message=f"Evolution task started. Max iterations: {request.max_iterations}",
    )


@router.get("/status/{task_id}", response_model=EvolveStatusResponse)
async def get_evolution_status(
    task_id: str,
    _: str = Depends(verify_api_key),
) -> EvolveStatusResponse:
    """Get the status of an evolution task."""
    if task_id not in _tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    task = _tasks[task_id]

    return EvolveStatusResponse(
        task_id=task_id,
        status=task["status"],
        current_iteration=task["current_iteration"],
        max_iterations=task["max_iterations"],
        objective=task["objective"],
        changes=task["changes"],
        test_results=task["test_results"],
        error=task["error"],
        started_at=task["started_at"],
        completed_at=task["completed_at"],
    )


@router.post("/analyze", response_model=dict)
async def analyze_code(
    request: EvolveRequest,
    _: str = Depends(verify_api_key),
) -> dict:
    """
    Analyze code for potential improvements (synchronous).

    Returns analysis without making changes.
    """
    prompt = f"""Analyze the code at '{request.target_path}'.

Objective: {request.objective}
Constraints: {', '.join(request.constraints) if request.constraints else 'None'}

Please provide:
1. Current state assessment
2. Identified issues or improvement opportunities
3. Recommended changes with priority
4. Potential risks of changes

Do NOT make any changes - analysis only."""

    try:
        response = await claude_client.query(
            prompt=prompt,
            allowed_tools=["Read", "Glob", "Grep"],
            max_turns=5,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    return {
        "analysis": response.result,
        "session_id": response.session_id,
        "duration_ms": response.duration_ms,
    }
