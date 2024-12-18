# Mods SDK

This repo includes a Python SDK with weave api helpers.  If you find yourself implementing custom logic for interacting with weave, consider adding it to here.  This module is automatically installed in the mod environment and available by importing `mods`.  When running in dev mode, changes will be reflected in the container.

## Features

### Streamlit Components

The SDK provides several pre-built Streamlit components:

- `selectbox`: Enhanced selection interface with support for querying different types from weave (OP, DATASET, MODEL, OBJECT)
- `multiselect`: Multi-selection component for handling multiple items
- `chat_thread`: Chat interface component
- `tracetable`: Data visualization component for traces/tables

### API Integration

Built-in API utilities for data querying and manipulation:

- `get_calls`: Retrieve call data
- `get_ops`: Get operations information
- `get_objects`: Fetch object data
- `resolve_refs`: Resolve reference data

## Quick Start

Here's an example of building a dataset selection interface with the SDK:

```python
from mods.streamlit import DATASET, selectbox

dataset = selectbox(DATASET, "Select a dataset")
```
