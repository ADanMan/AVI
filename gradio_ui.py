"""
Advanced Gradio Interface for AVI System.

Provides comprehensive UI with:
- Admin mode: Full control, debugging, rule viewing
- User mode: Simple chat interface
- System management and monitoring
"""

import json
import os
from typing import Any, Generator

import gradio as gr
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_URL = os.getenv("AVI_API_URL", "http://localhost:8000")
API_KEY = os.getenv("AVI_API_KEY", "")

# Global state for runtime API key
_runtime_api_key = None

# Global HTTP client
client = httpx.Client(timeout=60.0)


def get_api_key() -> str:
    """Get current API key (runtime or env)."""
    return _runtime_api_key or API_KEY


def set_api_key(key: str) -> str:
    """Set runtime API key."""
    global _runtime_api_key
    _runtime_api_key = key.strip() if key else None
    if _runtime_api_key:
        return f"✅ API Key set successfully (length: {len(_runtime_api_key)})"
    else:
        return "ℹ️ API Key cleared, using environment variable if set"



# ============================================================================
# API Helper Functions
# ============================================================================

def call_api(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Call AVI API endpoint."""
    headers = {"Content-Type": "application/json"}
    api_key = get_api_key()
    if api_key:
        headers["X-API-Key"] = api_key

    url = f"{API_URL}{endpoint}"

    try:
        if method == "GET":
            response = client.get(url, headers=headers)
        elif method == "POST":
            response = client.post(url, headers=headers, json=data)
        elif method == "PUT":
            response = client.put(url, headers=headers, json=data)
        else:
            return {"error": f"Unsupported method: {method}"}

        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
    except httpx.ConnectError:
        return {"error": f"Cannot connect to API at {API_URL}"}
    except Exception as e:
        return {"error": str(e)}


def query_non_stream(query: str, use_rag: bool = True, use_safety: bool = True, use_cache: bool = False) -> tuple[str, dict]:
    """Non-streaming query to API using /query endpoint.

    Returns:
        tuple: (response_text, full_result_dict)
    """
    payload = {
        "query": query,
        "use_llm_filter": use_safety,
        "use_linked_docs": use_rag,
        "use_cache": use_cache,
    }

    result = call_api("/api/v1/query", method="POST", data=payload)

    if "error" in result:
        return f"❌ Error: {result['error']}", result

    # Extract response text
    response_text = result.get("response", "")
    if not response_text:
        # Try alternative field names
        response_text = result.get("text", result.get("answer", str(result)))

    return response_text, result


def stream_query(
    query: str,
    use_rag: bool = True,
    use_safety: bool = True,
    use_cache: bool = False,
) -> Generator[tuple[str, dict], None, None]:
    """Stream query response from API using /query/stream endpoint.

    Yields:
        tuple: (accumulated_response_text, metadata_dict)
    """
    payload = {
        "query": query,
        "use_llm_filter": use_safety,
        "use_linked_docs": use_rag,
        "use_cache": use_cache,
    }

    headers = {"Content-Type": "application/json"}
    api_key = get_api_key()
    if api_key:
        headers["X-API-Key"] = api_key

    try:
        # Use the dedicated streaming endpoint
        url = f"{API_URL}/api/v1/query/stream"
        with client.stream(
            "POST",
            url,
            json=payload,
            headers=headers,
        ) as response:
            response.raise_for_status()

            full_response = ""
            metadata = {"events": [], "metrics": None}

            for line in response.iter_lines():
                # Decode bytes to string
                if isinstance(line, bytes):
                    line = line.decode('utf-8')

                # Skip empty lines
                if not line.strip():
                    continue

                # Parse SSE format
                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix
                    if data == "[DONE]":
                        break

                    try:
                        # Parse JSON to properly decode Unicode
                        json_data = json.loads(data)

                        if "chunk" in json_data:
                            # Text chunk - extract and accumulate
                            chunk_text = json_data["chunk"]
                            full_response += chunk_text
                            yield full_response, metadata
                        elif "event" in json_data:
                            # Event (metrics, etc) - store in metadata
                            metadata["events"].append(json_data)
                            if json_data.get("event") == "guard_metrics":
                                metadata["metrics"] = json_data.get("metrics", {})
                                metadata["mode"] = json_data.get("mode", "unknown")
                    except json.JSONDecodeError:
                        # If not JSON, treat as plain text
                        full_response += data
                        yield full_response, metadata

    except httpx.HTTPStatusError as e:
        yield f"❌ Error: HTTP {e.response.status_code}\n{e.response.text}", {}
    except httpx.ConnectError:
        yield f"❌ Cannot connect to API at {API_URL}", {}
    except Exception as e:
        yield f"❌ Error: {str(e)}", {}


# ============================================================================
# System Management Functions
# ============================================================================

def get_system_status() -> dict:
    """Get current system status."""
    health = call_api("/api/v1/health")
    settings = call_api("/api/v1/settings")

    return {
        "health": health,
        "settings": settings,
    }


def toggle_rag(enabled: bool) -> str:
    """Enable/disable RAG system."""
    result = call_api(
        "/api/v1/settings/rag",
        method="POST",
        data={"enabled": enabled}
    )

    if "error" in result:
        return f"❌ Error: {result['error']}"
    return f"✅ RAG {'enabled' if enabled else 'disabled'}"


def toggle_safety(enabled: bool) -> str:
    """Enable/disable safety filters."""
    mode = "full" if enabled else "disabled"
    result = call_api(
        "/api/v1/settings/safety",
        method="POST",
        data={"mode": mode}
    )

    if "error" in result:
        return f"❌ Error: {result['error']}"
    return f"✅ Safety filters {'enabled' if enabled else 'disabled'}"


def get_rules_list() -> dict:
    """Get list of all filtering rules in JSON format."""
    result = call_api("/api/v1/rules")

    if "error" in result:
        return {"error": result['error'], "rules": []}

    if not result or not isinstance(result, list):
        return {"total": 0, "rules": []}

    # Return structured JSON for better display
    return {
        "total": len(result),
        "rules": result,
        "categories": list(set(r.get("category", "uncategorized") for r in result)),
    }


def get_documents_list() -> str:
    """Get list of all documents."""
    result = call_api("/api/v1/documents")

    if "error" in result:
        return f"❌ Error: {result['error']}"

    if not result:
        return "No documents found"

    output = "# 📄 Knowledge Documents\n\n"
    for doc in result[:20]:  # Limit to 20 for display
        output += f"## Document: {doc.get('id', 'N/A')}\n"
        output += f"**Text:** {doc.get('text', 'N/A')[:200]}...\n"
        output += f"**Category:** {doc.get('category', 'N/A')}\n\n"
        output += "---\n\n"

    if len(result) > 20:
        output += f"\n_Showing 20 of {len(result)} documents_"

    return output


def trigger_reindex() -> str:
    """Trigger system reindexing."""
    result = call_api("/api/v1/reindex", method="POST")

    if "error" in result:
        return f"❌ Error: {result['error']}"

    return f"✅ {result.get('message', 'Reindexing started')}"


def export_to_csv() -> str:
    """Export data to CSV."""
    result = call_api("/api/v1/export/csv", method="POST")

    if "error" in result:
        return f"❌ Error: {result['error']}"

    return f"✅ Exported:\n- {result.get('exported_rules', 0)} rules\n- {result.get('exported_documents', 0)} documents\n- {result.get('exported_links', 0)} links\n\nSaved to: {result.get('output_directory', 'N/A')}"


def upload_csv_files(rules_file, docs_file, links_file) -> tuple[str, str]:
    """Upload CSV files to the system.

    Returns:
        tuple: (upload_status, indexing_info)
    """
    if not all([rules_file, docs_file, links_file]):
        return "❌ All three CSV files are required (rules, documents, links)", "No files uploaded"

    headers = {}
    api_key = get_api_key()
    if api_key:
        headers["X-API-Key"] = api_key

    # Prepare files for upload - open them in binary mode
    opened_files = []  # Keep track of opened files for cleanup

    try:
        # Open all three files (all are required)
        rules_f = open(rules_file, "rb")
        docs_f = open(docs_file, "rb")
        links_f = open(links_file, "rb")
        opened_files.extend([rules_f, docs_f, links_f])

        files = {
            "rules_file": ("filter_rules.csv", rules_f, "text/csv"),
            "documents_file": ("vector_documents.csv", docs_f, "text/csv"),
            "links_file": ("links.csv", links_f, "text/csv"),
        }

        response = client.post(
            f"{API_URL}/api/v1/upload/csv",
            headers=headers,
            files=files,
        )
        response.raise_for_status()
        result = response.json()

        uploaded = result.get('uploaded_files', [])
        message = f"✅ Upload successful!\n\nUploaded files:\n"
        for f in uploaded:
            message += f"- {f}\n"
        message += f"\nSaved to: {result.get('saved_to', 'N/A')}\n"
        message += f"Indexing: {result.get('message', 'Started in background')}"

        indexing_info = "🔄 Indexing started in background. Check status below."

        return message, indexing_info

    except httpx.HTTPStatusError as e:
        error_msg = f"❌ Error: HTTP {e.response.status_code}\n{e.response.text}"
        return error_msg, "Upload failed"
    except httpx.ConnectError:
        error_msg = f"❌ Cannot connect to API at {API_URL}"
        return error_msg, "Upload failed"
    except Exception as e:
        error_msg = f"❌ Error: {str(e)}"
        return error_msg, "Upload failed"
    finally:
        # Clean up opened files
        for f in opened_files:
            try:
                f.close()
            except Exception:
                pass  # Ignore errors during cleanup


def get_indexing_status() -> dict:
    """Get current indexing status."""
    result = call_api("/api/v1/indexing/status")

    if "error" in result:
        return {
            "status": "error",
            "error": result["error"],
            "progress_percentage": 0,
        }

    # Extract status information
    status_data = result.get("status", {})

    return status_data


def format_indexing_status(status_dict: dict) -> str:
    """Format indexing status as readable text."""
    if "error" in status_dict:
        return f"❌ Error fetching status: {status_dict['error']}"

    status = status_dict.get("status", "unknown")
    progress = status_dict.get("progress_percentage", 0)
    current_op = status_dict.get("current_operation", "N/A")

    # Status icon
    status_icons = {
        "idle": "⚪",
        "in_progress": "🔄",
        "completed": "✅",
        "failed": "❌",
    }
    icon = status_icons.get(status, "❓")

    # Build status message
    message = f"{icon} **Status:** {status.upper()}\n"
    message += f"📊 **Progress:** {progress:.1f}%\n"
    message += f"🔧 **Current Operation:** {current_op}\n\n"

    # Add counts
    indexed_rules = status_dict.get("indexed_rules", 0)
    indexed_docs = status_dict.get("indexed_documents", 0)
    indexed_links = status_dict.get("indexed_links", 0)
    total_rules = status_dict.get("total_rules", 0)
    total_docs = status_dict.get("total_documents", 0)
    total_links = status_dict.get("total_links", 0)

    message += "### Indexed Items:\n"
    message += f"- **Rules:** {indexed_rules} / {total_rules}\n"
    message += f"- **Documents:** {indexed_docs} / {total_docs}\n"
    message += f"- **Links:** {indexed_links} / {total_links}\n\n"

    # Add timing info if available
    if status_dict.get("start_time"):
        message += f"⏱️ **Started:** {status_dict.get('start_time', 'N/A')}\n"
    if status_dict.get("end_time"):
        message += f"⏱️ **Ended:** {status_dict.get('end_time', 'N/A')}\n"
    if status_dict.get("duration_seconds"):
        duration = status_dict.get("duration_seconds", 0)
        message += f"⏱️ **Duration:** {duration:.2f}s\n"

    # Add error message if failed
    if status == "failed" and status_dict.get("error_message"):
        message += f"\n❌ **Error:** {status_dict.get('error_message')}\n"

    return message


# ============================================================================
# User Interface - User Mode
# ============================================================================

def create_user_interface():
    """Create simple user-facing chat interface."""
    with gr.Column():
        gr.Markdown(
            """
            # 💬 AVI Chat

            Ask me anything! I'm here to help with safe, accurate information.
            """
        )

        chatbot = gr.Chatbot(
            label="Chat",
            height=500,
            show_copy_button=True,
            avatar_images=(None, "🤖"),
        )

        with gr.Row():
            msg = gr.Textbox(
                label="Your message",
                placeholder="Type your message here...",
                lines=2,
                scale=4,
            )
            submit = gr.Button("Send 📤", variant="primary", scale=1)

        with gr.Row():
            stream_mode = gr.Checkbox(label="Stream Response", value=True, scale=1)
            use_cache = gr.Checkbox(label="Use Cache", value=False, scale=1)
            clear = gr.Button("Clear Chat 🗑️", scale=1)

        # Event handlers
        def user_respond(message, chat_history, stream_enabled, cache_enabled):
            """Handle user message in simple mode."""
            if not message.strip():
                return chat_history

            # Add user message
            chat_history.append([message, None])

            if stream_enabled:
                # Stream response
                for response, _ in stream_query(message, use_rag=True, use_safety=True, use_cache=cache_enabled):
                    chat_history[-1][1] = response
                    yield chat_history
            else:
                # Non-streaming response
                response, _ = query_non_stream(message, use_rag=True, use_safety=True, use_cache=cache_enabled)
                chat_history[-1][1] = response
                yield chat_history

        submit.click(
            user_respond,
            inputs=[msg, chatbot, stream_mode, use_cache],
            outputs=[chatbot],
        ).then(lambda: "", outputs=[msg])

        msg.submit(
            user_respond,
            inputs=[msg, chatbot, stream_mode, use_cache],
            outputs=[chatbot],
        ).then(lambda: "", outputs=[msg])

        clear.click(lambda: None, None, chatbot)


# ============================================================================
# Admin Interface - Admin Mode
# ============================================================================

def create_admin_interface():
    """Create comprehensive admin interface."""

    with gr.Row():
        # Left column: Chat
        with gr.Column(scale=2):
            gr.Markdown("# 🛠️ Admin Chat & Debug")

            chatbot = gr.Chatbot(
                label="Chat with Full Context",
                height=400,
                show_copy_button=True,
            )

            with gr.Row():
                msg = gr.Textbox(
                    label="Query",
                    placeholder="Type your message...",
                    lines=2,
                    scale=4,
                )
                submit = gr.Button("Send", variant="primary", scale=1)

            # Admin controls
            with gr.Row():
                use_rag = gr.Checkbox(label="RAG", value=True)
                use_safety = gr.Checkbox(label="Safety", value=True)
                stream_mode = gr.Checkbox(label="Stream", value=True)
                use_cache = gr.Checkbox(label="Cache", value=False)
                clear = gr.Button("Clear")

            # Retrieved context display
            gr.Markdown("### 📚 Retrieved Context")
            retrieved_context = gr.JSON(
                label="RAG Retrieved Documents",
                value=None,
            )

            # Applied rules display
            gr.Markdown("### 🛡️ Applied Safety Rules")
            applied_rules = gr.JSON(
                label="Safety Rules & Filtering Results",
                value=None,
            )

            # Debug info display
            gr.Markdown("### 🔍 Debug Info (JSON)")
            debug_info = gr.JSON(
                label="Streaming Metrics & Events",
                value=None,
            )

        # Right column: System Management
        with gr.Column(scale=1):
            gr.Markdown("# ⚙️ System Control")

            # API Key configuration
            with gr.Accordion("🔑 API Authentication", open=True):
                api_key_input = gr.Textbox(
                    label="API Key",
                    placeholder="Enter your API key (optional)",
                    type="password",
                    value=API_KEY if API_KEY else "",
                )
                api_key_btn = gr.Button("Set API Key 🔐", size="sm")
                api_key_status = gr.Textbox(label="Status", interactive=False, lines=2)

                api_key_btn.click(
                    set_api_key,
                    inputs=[api_key_input],
                    outputs=[api_key_status]
                )

                gr.Markdown(
                    """
                    ℹ️ **Tips:**
                    - Leave empty to use environment variable
                    - Set once and use for all requests
                    - Key is stored in memory (not saved)
                    """
                )

            # System status
            with gr.Accordion("📊 System Status", open=False):
                status_display = gr.JSON(label="Current Status")
                refresh_status = gr.Button("Refresh Status 🔄", size="sm")

                def refresh_status_fn():
                    return get_system_status()

                refresh_status.click(refresh_status_fn, outputs=[status_display])

            # System toggles
            with gr.Accordion("🎛️ System Toggles", open=False):
                gr.Markdown("**RAG System**")
                rag_toggle = gr.Checkbox(label="Enable RAG", value=True)
                rag_status = gr.Textbox(label="Status", interactive=False)

                rag_toggle.change(
                    toggle_rag,
                    inputs=[rag_toggle],
                    outputs=[rag_status]
                )

                gr.Markdown("**Safety Filters**")
                safety_toggle = gr.Checkbox(label="Enable Safety", value=True)
                safety_status = gr.Textbox(label="Status", interactive=False)

                safety_toggle.change(
                    toggle_safety,
                    inputs=[safety_toggle],
                    outputs=[safety_status]
                )

            # Data management
            with gr.Accordion("📁 Data Management", open=False):
                gr.Markdown("**Upload CSV Files**")
                gr.Markdown(
                    """
                    Upload CSV files to index. Required formats:
                    - **Rules**: `id, text, risk_level` (+ optional: category, threshold)
                    - **Documents**: `id, text` (+ optional: category, source)
                    - **Links**: `rule_id, document_id, is_approved`
                    """
                )

                rules_upload = gr.File(label="Rules CSV", file_types=[".csv"])
                docs_upload = gr.File(label="Documents CSV", file_types=[".csv"])
                links_upload = gr.File(label="Links CSV", file_types=[".csv"])

                upload_btn = gr.Button("Upload & Index 📤", variant="primary", size="sm")
                upload_status = gr.Textbox(label="Upload Status", interactive=False, lines=5)

                gr.Markdown("---")
                gr.Markdown("**Indexing Status & Progress**")

                with gr.Row():
                    check_status_btn = gr.Button("Check Status 🔍", size="sm", variant="secondary")
                    auto_refresh = gr.Checkbox(label="Auto-refresh (5s)", value=False, scale=1)

                indexing_status_display = gr.Markdown(
                    value="⚪ No indexing operation running",
                    label="Indexing Progress"
                )

                indexing_metadata = gr.JSON(
                    label="Indexing Metadata (JSON)",
                    value=None,
                )

                # Upload handler
                def handle_upload(rules_file, docs_file, links_file):
                    upload_msg, indexing_msg = upload_csv_files(rules_file, docs_file, links_file)
                    # Also get initial status
                    status_dict = get_indexing_status()
                    status_text = format_indexing_status(status_dict)
                    return upload_msg, status_text, status_dict

                upload_btn.click(
                    handle_upload,
                    inputs=[rules_upload, docs_upload, links_upload],
                    outputs=[upload_status, indexing_status_display, indexing_metadata]
                )

                # Status check handler
                def check_status():
                    status_dict = get_indexing_status()
                    status_text = format_indexing_status(status_dict)
                    return status_text, status_dict

                check_status_btn.click(
                    check_status,
                    outputs=[indexing_status_display, indexing_metadata]
                )

                # Auto-refresh handler
                def auto_refresh_status(auto_refresh_enabled):
                    """Auto-refresh status every 5 seconds when enabled."""
                    import time
                    if auto_refresh_enabled:
                        while auto_refresh_enabled:
                            status_dict = get_indexing_status()
                            status_text = format_indexing_status(status_dict)
                            yield status_text, status_dict

                            # Stop auto-refresh if indexing is not in progress
                            if status_dict.get("status") not in ["in_progress"]:
                                break

                            time.sleep(5)

                # Note: Auto-refresh is a bit tricky with Gradio
                # For now, users can manually click "Check Status"

                gr.Markdown("---")
                gr.Markdown("**Data Operations**")

                reindex_btn = gr.Button("Trigger Reindex 🔄", size="sm")
                reindex_status = gr.Textbox(label="Reindex Status", interactive=False)

                def handle_reindex():
                    msg = trigger_reindex()
                    # Also get status
                    status_dict = get_indexing_status()
                    status_text = format_indexing_status(status_dict)
                    return msg, status_text, status_dict

                reindex_btn.click(
                    handle_reindex,
                    outputs=[reindex_status, indexing_status_display, indexing_metadata]
                )

                export_btn = gr.Button("Export to CSV 💾", size="sm")
                export_status = gr.Textbox(label="Export Status", interactive=False)

                export_btn.click(
                    export_to_csv,
                    outputs=[export_status]
                )

            # View documents
            with gr.Accordion("📄 View Documents", open=False):
                view_docs_btn = gr.Button("Load Documents 📄", size="sm")
                docs_display = gr.Markdown()

                view_docs_btn.click(
                    get_documents_list,
                    outputs=[docs_display]
                )

            # Quick links to services
            with gr.Accordion("🔗 Service Links", open=False):
                gr.Markdown("**AVI Services**")
                gr.Markdown(f"[📖 API Documentation]({API_URL}/docs)")
                gr.Markdown(f"[❤️ Health Check]({API_URL}/api/v1/health)")
                gr.Markdown(f"[⚙️ Settings]({API_URL}/api/v1/settings)")

                gr.Markdown("---")
                gr.Markdown("**Monitoring & Metrics**")
                gr.Markdown("[📊 Prometheus](http://localhost:9090)")
                gr.Markdown("[📈 Grafana](http://localhost:3000)")
                gr.Markdown("[🔍 Jaeger (Traces)](http://localhost:16686)")
                gr.Markdown("[📉 MLflow](http://localhost:5000)")

                gr.Markdown("---")
                gr.Markdown("**Databases**")
                gr.Markdown("[🗄️ Qdrant (Vector DB)](http://localhost:6333/dashboard)")
                gr.Markdown("[💾 Redis](http://localhost:6379)")

                gr.Markdown("---")
                gr.Markdown(
                    f"""
                    **Connection Info**
                    - API: `{API_URL}`
                    - Auth: {"✅ Enabled" if API_KEY else "❌ Disabled"}
                    """
                )

    # Admin chat event handler
    def admin_respond(message, chat_history, use_rag, use_safety, stream_enabled, cache_enabled):
        """Handle admin chat with full debugging info."""
        if not message.strip():
            return chat_history, None, None, None

        # Add user message
        chat_history.append([message, None])

        if stream_enabled:
            # Stream response
            last_metadata = {}
            for response, metadata in stream_query(message, use_rag, use_safety, cache_enabled):
                chat_history[-1][1] = response
                last_metadata = metadata

                # Extract debug info from metadata
                debug_data = {
                    "mode": metadata.get("mode", "N/A"),
                    "metrics": metadata.get("metrics", {}),
                    "events": metadata.get("events", []),
                }

                # For now, context and rules are in metadata (if API provides them)
                context_data = metadata.get("retrieved_context", None)
                rules_data = metadata.get("applied_rules", metadata.get("metrics", None))

                yield chat_history, context_data, rules_data, debug_data
        else:
            # Non-streaming response
            response, result = query_non_stream(message, use_rag, use_safety, cache_enabled)
            chat_history[-1][1] = response

            # Extract context and rules from result
            context_data = None
            rules_data = None
            debug_data = result

            # Try to extract retrieved documents info
            if "retrieved_documents" in result:
                context_data = result["retrieved_documents"]

            # Try to extract filtering info
            if "input_filter_result" in result or "output_filter_result" in result:
                rules_data = {
                    "input_filter": result.get("input_filter_result"),
                    "output_filter": result.get("output_filter_result"),
                }

            yield chat_history, context_data, rules_data, debug_data

    submit.click(
        admin_respond,
        inputs=[msg, chatbot, use_rag, use_safety, stream_mode, use_cache],
        outputs=[chatbot, retrieved_context, applied_rules, debug_info],
    ).then(lambda: "", outputs=[msg])

    msg.submit(
        admin_respond,
        inputs=[msg, chatbot, use_rag, use_safety, stream_mode, use_cache],
        outputs=[chatbot, retrieved_context, applied_rules, debug_info],
    ).then(lambda: "", outputs=[msg])

    clear.click(lambda: None, None, chatbot)


# ============================================================================
# Main Application
# ============================================================================

def create_app():
    """Create main Gradio application with tabs."""

    with gr.Blocks(
        title="AVI Interface",
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="slate",
        ),
        css="""
        .gradio-container {
            max-width: 1400px !important;
        }
        """
    ) as app:

        gr.Markdown(
            """
            # 🛡️ AVI - Agreement Validation Interface

            **Advanced AI Safety & RAG System**
            """
        )

        with gr.Tabs() as tabs:
            with gr.Tab("💬 User Chat", id=0):
                create_user_interface()

            with gr.Tab("🛠️ Admin Panel", id=1):
                create_admin_interface()

            with gr.Tab("📊 System Metrics", id=2):
                gr.Markdown("# 📈 System Metrics")
                gr.Markdown(
                    f"""
                    View detailed system metrics and monitoring:

                    - [Prometheus Metrics]({API_URL}/metrics)
                    - [Health Check]({API_URL}/api/v1/health)
                    - [Indexing Status]({API_URL}/api/v1/indexing/status)

                    Connect Grafana to visualize metrics in real-time.
                    """
                )

    return app


if __name__ == "__main__":
    app = create_app()

    print(f"""
    ╔═══════════════════════════════════════════════════════════╗
    ║            AVI Advanced Gradio Interface                  ║
    ╠═══════════════════════════════════════════════════════════╣
    ║ • API URL:    {API_URL:<44} ║
    ║ • Auth:       {"Enabled" if API_KEY else "Disabled":<44} ║
    ║                                                           ║
    ║ Modes Available:                                          ║
    ║   💬 User Chat  - Simple interface for end users        ║
    ║   🛠️ Admin Panel - Full control and debugging           ║
    ║   📊 Metrics    - System monitoring                      ║
    ╚═══════════════════════════════════════════════════════════╝

    Starting interface on http://0.0.0.0:7860
    """)

    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_api=False,
    )
