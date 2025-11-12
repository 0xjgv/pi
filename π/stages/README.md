# Workflow Stages

Each stage in the workflow system runs as an independent Python script.

## Structure

All stages follow this pattern:

1. Inherit from `StageRunner` base class
2. Implement `parse_args()` to handle CLI arguments
3. Implement `run_stage()` to execute logic
4. Return `StageResult` with structured output
5. Use `asyncio.run(main())` as entry point

## Data Contract

### Input (CLI Arguments)
Common arguments across stages:
- `workflow_id`: Unique identifier for this workflow run
- `user_query`: The user's original request
- `log_dir`: Directory for log files
- `thoughts_dir`: Directory for generated documents
- `previous_result`: Result from previous stage

### Output (JSON on stdout)
```json
{
  "status": "success",
  "result": "Final message from agent",
  "document": "/path/to/document.md",
  "stats": {
    "total_tools": 42,
    "errors": 0,
    "tool_counts": {"Read": 15, "Grep": 10}
  }
}
```

## Adding a New Stage

1. Create `π/stages/new_stage.py`
2. Subclass `StageRunner`
3. Implement required methods
4. Add corresponding prompt file in `π/prompts/`
5. Update `π/workflow.py` to invoke the stage
6. Add test in `tests/integration/`

## Testing Stages Independently

Each stage can be tested standalone:

```bash
python π/stages/research.py \
  <workflow-id> \
  "user query" \
  /path/to/logs \
  /path/to/thoughts
```

The stage will output JSON result to stdout and progress to stderr.
