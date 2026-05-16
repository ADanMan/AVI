# Indexing Status API

This document describes the indexing status tracking functionality added in Task 2.1 of the refactoring plan.

## Overview

The indexing status API allows clients to monitor the progress of data reindexing operations in real-time. This is essential for providing user feedback during potentially long-running indexing operations.

## Architecture

### Components

1. **IndexingStateManager** (`src/services/indexing_state.py`)
   - Singleton state manager for tracking indexing progress
   - Thread-safe with async lock
   - Maintains current state, progress, counts, timing, and errors

2. **IndexingService** (`src/services/indexing_service.py`)
   - Updated to integrate with IndexingStateManager
   - Tracks progress through all indexing phases
   - Updates state at key checkpoints

3. **API Endpoints** (`src/api/routes.py`)
   - GET `/api/v1/indexing/status` - Get current status
   - GET `/api/v1/indexing/status/stream` - Stream real-time updates (SSE)
   - POST `/api/v1/reindex` - Start reindexing (updated)

4. **Data Models** (`src/models/schemas.py`)
   - `IndexingStatus` - Status information model
   - `IndexingStatusResponse` - API response wrapper

## API Endpoints

### GET /api/v1/indexing/status

Returns the current indexing status.

**Response:**
```json
{
  "status": {
    "status": "in_progress",
    "progress_percentage": 45.5,
    "indexed_rules": 25,
    "indexed_documents": 150,
    "indexed_links": 75,
    "total_rules": 50,
    "total_documents": 300,
    "total_links": 150,
    "start_time": "2025-11-13T10:00:00Z",
    "end_time": null,
    "duration_seconds": 120.5,
    "error_message": null,
    "current_operation": "Indexing documents"
  },
  "timestamp": "2025-11-13T10:02:30Z"
}
```

**Status Values:**
- `idle` - No indexing operation is running
- `in_progress` - Indexing is currently running
- `completed` - Indexing completed successfully
- `failed` - Indexing failed with an error

### GET /api/v1/indexing/status/stream

Streams real-time indexing status updates using Server-Sent Events (SSE).

**Usage Example (JavaScript):**
```javascript
const eventSource = new EventSource('/api/v1/indexing/status/stream');

eventSource.onmessage = (event) => {
  const status = JSON.parse(event.data);
  console.log('Progress:', status.progress_percentage + '%');
  console.log('Operation:', status.current_operation);
};

eventSource.addEventListener('end', (event) => {
  console.log('Indexing finished:', event.data);
  eventSource.close();
});

eventSource.onerror = (error) => {
  console.error('SSE error:', error);
  eventSource.close();
};
```

**Stream Format:**
```
data: {"status": "in_progress", "progress_percentage": 10.0, ...}

data: {"status": "in_progress", "progress_percentage": 50.0, ...}

data: {"status": "completed", "progress_percentage": 100.0, ...}

event: end
data: {"status": "completed"}
```

**Features:**
- Updates every 500ms while indexing is in progress
- Automatically closes stream when indexing completes or fails
- Only sends updates when status changes (efficient)

### POST /api/v1/reindex

Starts a background reindexing operation. Updated to check if indexing is already in progress.

**Behavior Changes:**
- Returns 409 if another indexing operation is already running
- Prevents concurrent indexing operations

**Response (Success):**
```json
{
  "status": "started",
  "message": "Reindexing started in the background"
}
```

**Response (Already in Progress):**
```json
{
  "detail": "Reindexing is already in progress. Please wait for it to complete."
}
```
Status Code: 409 Conflict

## Indexing Phases

The indexing operation goes through these phases, each with progress updates:

1. **Initialization**
   - Load CSV files
   - Calculate totals
   - Update: `current_operation: "Starting indexing"`

2. **Link Validation** (if links exist)
   - Validate links CSV structure
   - Update: `current_operation: "Validating links CSV"`

3. **Rules Indexing**
   - Reset rule collection
   - Add rules to vector database
   - Update: `current_operation: "Indexing rules"`
   - Progress: `indexed_rules: N`

4. **Documents Indexing**
   - Reset documents collection
   - Add documents to vector database
   - Update: `current_operation: "Indexing documents"`
   - Progress: `indexed_documents: N`

5. **Links Creation**
   - Reset links collection
   - Create rule-document links
   - Update: `current_operation: "Creating links (N/total)"`
   - Progress: `indexed_links: N` (updated every 10 links)

6. **Completion**
   - Mark as completed
   - Update: `status: "completed"`, `progress_percentage: 100.0`

## Error Handling

If any phase fails:
- Status changes to `"failed"`
- `error_message` contains error details
- `end_time` is set
- Progress tracking stops

Example error response:
```json
{
  "status": {
    "status": "failed",
    "progress_percentage": 25.0,
    "indexed_rules": 50,
    "indexed_documents": 0,
    "indexed_links": 0,
    "error_message": "Links CSV errors: ['Duplicate rule_id/document_id pairs found.']",
    "current_operation": "Indexing failed"
  }
}
```

## State Management

### IndexingStateManager

Singleton class that maintains global indexing state across all requests.

**Key Methods:**
- `start_indexing(total_rules, total_documents, total_links)` - Initialize indexing
- `update_progress(indexed_rules, indexed_documents, indexed_links, current_operation)` - Update progress
- `complete_indexing()` - Mark as completed
- `fail_indexing(error_message)` - Mark as failed
- `get_status()` - Get current status (async, returns IndexingStatus)
- `is_indexing_in_progress()` - Check if indexing is running (sync)

**Thread Safety:**
- Uses `asyncio.Lock` for thread-safe state updates
- Safe for concurrent access from multiple requests

## Integration with UI

The UI can use these APIs to provide user feedback:

1. **Polling Approach** (Simple)
   ```javascript
   async function checkStatus() {
     const response = await fetch('/api/v1/indexing/status');
     const data = await response.json();
     updateUI(data.status);

     if (data.status.status === 'in_progress') {
       setTimeout(checkStatus, 1000); // Poll every second
     }
   }
   ```

2. **SSE Approach** (Recommended)
   ```javascript
   const eventSource = new EventSource('/api/v1/indexing/status/stream');

   eventSource.onmessage = (event) => {
     const status = JSON.parse(event.data);
     updateProgressBar(status.progress_percentage);
     updateStatusText(status.current_operation);
   };
   ```

## Example Usage Flow

1. User clicks "Reindex" button in UI
2. UI calls `POST /api/v1/reindex`
3. UI opens SSE connection to `/api/v1/indexing/status/stream`
4. UI receives periodic updates and displays progress bar
5. When indexing completes, stream closes automatically
6. UI shows success/failure message

## Testing

To test the indexing status API:

1. **Start indexing:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/reindex
   ```

2. **Check status:**
   ```bash
   curl http://localhost:8000/api/v1/indexing/status
   ```

3. **Stream status (using curl):**
   ```bash
   curl -N http://localhost:8000/api/v1/indexing/status/stream
   ```

4. **Try concurrent indexing (should fail):**
   ```bash
   curl -X POST http://localhost:8000/api/v1/reindex
   # Should return 409 Conflict if already running
   ```

## Performance Considerations

- **Memory:** State manager is lightweight, storing only current state (~1KB)
- **CPU:** Progress updates are minimal, only updating counters
- **Network:** SSE stream sends updates only when state changes (efficient)
- **Concurrency:** Lock ensures thread-safety without performance penalty

## Future Enhancements

Potential improvements for future versions:

1. **Persistent State** - Store state in Redis for multi-instance deployments
2. **Historical Tracking** - Keep history of past indexing operations
3. **Cancellation** - Allow users to cancel in-progress indexing
4. **Partial Reindexing** - Support reindexing only specific collections
5. **Progress Estimation** - More accurate time remaining calculations
6. **WebSocket Support** - Alternative to SSE for bi-directional communication
7. **Metrics Integration** - Export indexing metrics to Prometheus

## Related Documentation

- [INDEXING_PROCESS.md](./INDEXING_PROCESS.md) - Detailed indexing process documentation
- [API Documentation](../README.md) - General API documentation
- [REFACTORING_PLAN.md](../REFACTORING_PLAN.md) - Task 2.1 specification

## Version

**Implemented:** 2025-11-13
**Task:** 2.1 - Реализация статуса индексации
**Status:** ✅ Complete
