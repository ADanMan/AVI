# Missing API Endpoints - Implementation Plan

Based on validation pipeline results, these endpoints are called by the frontend but not implemented in the backend.

## Priority: 🔴 HIGH (Blocking Functionality)

These endpoints are critical for core functionality:

###  1. Chat Endpoints

**POST /api/v1/chat/complete**
- **Purpose:** Non-streaming chat completion
- **Request:**
  ```json
  {
    "message": "string",
    "conversation_id": "string" (optional),
    "context": {} (optional)
  }
  ```
- **Response:**
  ```json
  {
    "response": "string",
    "conversation_id": "string",
    "metadata": {}
  }
  ```
- **Implementation File:** `src/api/chat_routes.py`
- **Estimate:** 2-3 hours

**POST /api/v1/chat/stream**
- **Purpose:** Streaming chat responses
- **Request:** Same as above
- **Response:** Server-Sent Events (SSE) stream
- **Implementation File:** `src/api/chat_routes.py`
- **Estimate:** 3-4 hours

### 2. Settings Endpoints

**POST /api/v1/settings/llm/:param**
- **Purpose:** Update specific LLM setting
- **Path Param:** Setting name (e.g., "temperature", "max_tokens")
- **Implementation File:** `src/api/settings_routes.py`
- **Estimate:** 1 hour

**POST /api/v1/settings/rag**
- **Purpose:** Update RAG configuration
- **Implementation File:** `src/api/settings_routes.py`
- **Estimate:** 1 hour

**POST /api/v1/settings/cache**
- **Purpose:** Update cache settings
- **Implementation File:** `src/api/settings_routes.py`
- **Estimate:** 1 hour

**POST /api/v1/settings/filtering**
- **Purpose:** Update filter settings
- **Implementation File:** `src/api/settings_routes.py`
- **Estimate:** 1 hour

**POST /api/v1/settings/safety**
- **Purpose:** Update safety settings
- **Implementation File:** `src/api/settings_routes.py`
- **Estimate:** 1 hour

**POST /api/v1/settings/monitoring**
- **Purpose:** Update monitoring configuration
- **Implementation File:** `src/api/settings_routes.py`
- **Estimate:** 1 hour

**POST /api/v1/settings/rate-limit**
- **Purpose:** Update rate limiting settings
- **Implementation File:** `src/api/settings_routes.py`
- **Estimate:** 1 hour

**POST /api/v1/settings/indexing**
- **Purpose:** Update indexing configuration
- **Implementation File:** `src/api/settings_routes.py`
- **Estimate:** 1 hour

**POST /api/v1/settings/reset**
- **Purpose:** Reset all settings to defaults
- **Implementation File:** `src/api/settings_routes.py`
- **Estimate:** 30 minutes

**POST /api/v1/settings/reset/:param**
- **Purpose:** Reset specific setting to default
- **Path Param:** Setting category
- **Implementation File:** `src/api/settings_routes.py`
- **Estimate:** 30 minutes

### 3. Data Management Endpoints

**POST /api/v1/reindex**
- **Purpose:** Trigger reindexing of vector database
- **Implementation File:** `src/api/routes.py`
- **Estimate:** 2 hours

### 4. Safety Endpoints

**POST /api/v1/safety/check**
- **Purpose:** Manual safety check for content
- **Request:**
  ```json
  {
    "text": "string",
    "context": {} (optional)
  }
  ```
- **Response:**
  ```json
  {
    "safe": boolean,
    "score": number,
    "reasons": []
  }
  ```
- **Implementation File:** `src/api/routes.py` or new `safety_routes.py`
- **Estimate:** 2-3 hours

### 5. Experiments Endpoints

**POST /api/v1/experiments/run**
- **Purpose:** Run experiment/benchmark
- **Implementation File:** `src/api/experiments_routes.py`
- **Estimate:** 3-4 hours

**POST /api/v1/experiments/compare**
- **Purpose:** Compare multiple experiments
- **Implementation File:** `src/api/experiments_routes.py`
- **Estimate:** 2-3 hours

### 6. Filter Configuration

**PUT /api/v1/filters/config**
- **Purpose:** Update filter configuration
- **Implementation File:** `src/api/filter_config_routes.py`
- **Estimate:** 1-2 hours

## Implementation Strategy

### Phase 1: Core Settings (1 day)
1. Create base settings update handler
2. Implement individual setting endpoints
3. Add validation and error handling
4. Test with frontend

**Files to modify:**
- `src/api/settings_routes.py`
- `config/settings.py` (if needed)

### Phase 2: Chat Endpoints (1 day)
1. Implement non-streaming endpoint
2. Add streaming endpoint
3. Connect to existing chat service
4. Test streaming functionality

**Files to modify:**
- `src/api/chat_routes.py`
- May need to create new service layer

### Phase 3: Data & Safety (1 day)
1. Implement reindex endpoint
2. Add safety check endpoint
3. Test with actual data
4. Add proper error handling

**Files to create/modify:**
- `src/api/safety_routes.py` (new)
- `src/api/routes.py` (modify)

### Phase 4: Experiments & Filters (1 day)
1. Implement experiment endpoints
2. Add filter config endpoint
3. Integration with MLflow
4. Testing

**Files to modify:**
- `src/api/experiments_routes.py`
- `src/api/filter_config_routes.py`

## Code Templates

### Settings Endpoint Template

```python
# src/api/settings_routes.py

@router.post("/api/v1/settings/{category}")
async def update_setting(
    category: str,
    request: Request,
    settings_update: dict = Body(...)
):
    """Update specific category of settings"""
    try:
        # Validate category
        valid_categories = ["llm", "rag", "cache", "filtering", "safety", "monitoring", "rate-limit", "indexing"]
        if category not in valid_categories:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

        # Update settings
        updated_settings = await update_category_settings(category, settings_update)

        return {
            "status": "success",
            "category": category,
            "settings": updated_settings
        }
    except Exception as e:
        logger.error(f"Error updating {category} settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Chat Endpoint Template

```python
# src/api/chat_routes.py

@router.post("/api/v1/chat/complete")
async def chat_complete(
    request: ChatRequest,
    background_tasks: BackgroundTasks
):
    """Non-streaming chat completion"""
    try:
        # Process chat request
        response = await chat_service.complete(
            message=request.message,
            conversation_id=request.conversation_id,
            context=request.context
        )

        return {
            "response": response.text,
            "conversation_id": response.conversation_id,
            "metadata": response.metadata
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat completion"""
    async def generate():
        try:
            async for chunk in chat_service.stream(
                message=request.message,
                conversation_id=request.conversation_id
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
```

## Testing Plan

For each endpoint:

1. **Unit Tests**
   ```python
   def test_update_llm_settings():
       response = client.post("/api/v1/settings/llm", json={"temperature": 0.7})
       assert response.status_code == 200
   ```

2. **Integration Tests**
   - Test with real services
   - Verify database updates
   - Check side effects

3. **E2E Tests**
   - Test from UI
   - Verify complete workflow
   - Check error handling

## Validation

After implementation, run:

```bash
# Validate API consistency
make validate-api

# Should show 0 high severity issues
```

## Rollout Plan

1. **Implement in feature branch**
   ```bash
   git checkout -b feature/missing-api-endpoints
   ```

2. **Test locally**
   ```bash
   # Start services
   docker-compose up -d

   # Run tests
   pytest tests/integration/test_new_endpoints.py

   # Validate
   make validate-api
   ```

3. **Create PR**
   - Include tests
   - Update documentation
   - Link to validation results

4. **Deploy incrementally**
   - Deploy to staging first
   - Test with frontend
   - Monitor errors
   - Deploy to production

## Effort Estimate

| Phase | Endpoints | Effort | Complexity |
|-------|-----------|--------|------------|
| Phase 1: Settings | 10 endpoints | 1 day | Low |
| Phase 2: Chat | 2 endpoints | 1 day | Medium |
| Phase 3: Data & Safety | 2 endpoints | 1 day | Medium |
| Phase 4: Experiments | 3 endpoints | 1 day | High |
| **Total** | **17 endpoints** | **4 days** | **Mixed** |

## Dependencies

- Existing services (chat, safety, experiments)
- Database schema updates (if needed)
- Frontend changes (if API contract changes)
- Documentation updates

## Risks & Mitigation

**Risk:** Breaking existing functionality
- **Mitigation:** Comprehensive tests, gradual rollout

**Risk:** Performance issues with new endpoints
- **Mitigation:** Load testing, monitoring

**Risk:** Security vulnerabilities
- **Mitigation:** Input validation, authentication checks

## Success Criteria

- [ ] All 17 endpoints implemented
- [ ] Validation pipeline shows 0 high severity API issues
- [ ] All tests passing
- [ ] Frontend successfully uses new endpoints
- [ ] Documentation updated
- [ ] Performance benchmarks met

## Next Steps

1. Review this plan with team
2. Prioritize endpoints based on frontend needs
3. Create implementation tickets
4. Start with Phase 1 (settings)
5. Iterate and deploy

---

**Created:** 2025-11-15
**Status:** Planning
**Owner:** Development Team
