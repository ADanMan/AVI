# Gradio Chat UI

Simple, ready-to-use chat interface for the AVI system using Gradio.

## Overview

The AVI project uses **Gradio** for a lightweight, production-ready chat interface. This replaces the previous React-based UI with a simpler solution that requires no build step.

## Features

- 💬 **Simple Chat Interface** - Clean, modern chat UI out of the box
- ⚙️ **Real-time Settings** - Toggle RAG and Safety filters on the fly
- 🔄 **Streaming Responses** - See AI responses as they're generated
- 📱 **Responsive Design** - Works on desktop and mobile
- 🚀 **No Build Required** - Just run the Python script
- 🔒 **API Authentication** - Optional API key support

## Quick Start

### Local Development

```bash
# 1. Start the API server (in one terminal)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 2. Start the Gradio UI (in another terminal)
python gradio_ui.py

# Or use Make
make run-ui
```

Access the chat at: **http://localhost:7860**

### Docker

```bash
# Start all services including Gradio UI
docker compose up --build

# Or just API + Gradio UI
docker compose up api gradio-ui
```

## Configuration

The Gradio UI can be configured via environment variables:

```bash
# .env file
AVI_API_URL=http://localhost:8000  # API endpoint
AVI_API_KEY=                        # Optional: API key for authentication
```

### Docker Environment

In Docker, the UI automatically connects to the API service:

```yaml
environment:
  AVI_API_URL: http://api:8000
  AVI_API_KEY: ${AVI_API_KEY:-}
```

## UI Components

### Chat Interface

- **Message Input** - Type your messages here
- **Send Button** - Submit your query
- **Chat History** - Scrollable conversation view
- **Copy Button** - Copy AI responses to clipboard

### Settings Panel

- **Use RAG Context** - Enable/disable retrieval-augmented generation
- **Use Safety Filters** - Enable/disable content safety checks

### System Info

The right panel displays:
- Current API URL
- Authentication status
- Links to API docs and health check

## Customization

### Changing the Theme

Edit `gradio_ui.py`:

```python
demo = gr.Blocks(
    title="AVI Chat",
    theme=gr.themes.Soft(),  # Try: Base, Monochrome, Glass, etc.
)
```

### Adding Features

The Gradio UI is designed to be simple and extendable. To add features:

1. Edit `gradio_ui.py`
2. Add new UI components using Gradio's API
3. Connect them to the AVI API endpoints

Example - adding model selection:

```python
with gr.Column(scale=1):
    model_selector = gr.Dropdown(
        choices=["gpt-4o-mini", "gpt-4o", "claude-3-haiku"],
        label="Model",
        value="gpt-4o-mini"
    )
```

## API Integration

The UI communicates with the AVI API via HTTP:

```python
# POST /api/v1/query
payload = {
    "query": message,
    "use_rag": use_rag,
    "use_safety_llm": use_safety,
    "stream": True,
}
```

Responses are streamed using Server-Sent Events (SSE).

## Troubleshooting

### UI Can't Connect to API

**Problem:** "Cannot connect to AVI API at http://localhost:8000"

**Solution:**
1. Check that API is running: `curl http://localhost:8000/health`
2. Verify API_URL in environment variables
3. Check firewall/port settings

### Authentication Errors

**Problem:** "HTTP 401 - Unauthorized"

**Solution:**
1. Set `AVI_API_KEY` environment variable
2. Or disable authentication in API settings

### Slow Responses

**Problem:** Chat responses are slow

**Solution:**
1. Check API performance: `/api/v1/health`
2. Disable RAG if not needed
3. Use a faster LLM model
4. Check network latency

## Comparison with Previous React UI

| Feature | React UI | Gradio UI |
|---------|----------|-----------|
| Setup Time | 5-10 min | < 1 min |
| Build Required | Yes (npm) | No |
| Dependencies | Node.js + npm | Python only |
| Code Size | ~20,000 lines | ~200 lines |
| Customization | High | Medium |
| Learning Curve | Steep | Gentle |
| Production Ready | Yes | Yes |

## Architecture

```
┌─────────────────┐
│  Gradio UI      │
│  Port: 7860     │
└────────┬────────┘
         │ HTTP/SSE
         │
┌────────▼────────┐
│  FastAPI        │
│  Port: 8000     │
└────────┬────────┘
         │
    ┌────┴─────┐
    │          │
┌───▼──┐  ┌───▼───┐
│ LLM  │  │ Vector│
│      │  │  DB   │
└──────┘  └───────┘
```

## Production Deployment

### Standalone

```bash
# Run behind a reverse proxy (nginx/caddy)
python gradio_ui.py
```

### Docker with Scaling

```yaml
services:
  gradio-ui:
    image: avi-gradio-ui:cpu
    deploy:
      replicas: 3  # Scale for high traffic
    ports:
      - "7860-7862:7860"
```

### Security

For production:
1. Enable API authentication
2. Use HTTPS (reverse proxy)
3. Set CORS policies
4. Rate limit API endpoints

## Development

### File Structure

```
gradio_ui.py          # Main UI file (~200 lines)
├── chat_with_avi()   # API communication
├── create_gradio_interface()  # UI layout
└── __main__          # Entry point
```

### Testing

```bash
# Manual testing
python gradio_ui.py

# Check API connection
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello", "stream": false}'
```

## Resources

- [Gradio Documentation](https://gradio.app/docs/)
- [Gradio Themes](https://gradio.app/guides/theming-guide/)
- [AVI API Documentation](./API.md)

## Migration from React UI

If you were using the previous React UI:

1. ✅ All chat functionality is preserved
2. ✅ Settings are accessible via UI toggles
3. ❌ Advanced analytics moved to API endpoints
4. ❌ System profiles selection - use API directly

For advanced features, use:
- **API Swagger UI**: http://localhost:8000/docs
- **Direct API calls**: See [API.md](./API.md)

## Future Enhancements

Planned improvements:
- [ ] Chat history persistence
- [ ] Export conversations
- [ ] Multi-turn context management
- [ ] Custom system prompts
- [ ] Model comparison mode

## Contributing

To improve the Gradio UI:

1. Fork the repository
2. Edit `gradio_ui.py`
3. Test locally
4. Submit a pull request

Keep it simple! The goal is a lightweight, easy-to-use interface.
