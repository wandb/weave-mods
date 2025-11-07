# VIBEZ - Neural Terminal Interface

A sci-fi themed terminal interface that runs the actual Claude Code CLI as a subprocess, featuring a cyberpunk aesthetic with full TTY emulation and project download capabilities.

## Features

### 🎨 **Sci-Fi Interface**
- Cinematic splash screen with glowing "VIBEZ" logo
- Cyberpunk color palette (grayish-brown gradients with neon green/orange accents)
- Animated grid background with CRT scanlines effects
- Full-screen immersive experience with floating controls

### 🤖 **Real Claude Code Integration**
- **Actual Claude Code CLI**: Runs the real `@anthropic-ai/claude-code` package as a subprocess
- **Complete Functionality**: Maintains ALL Claude Code features including:
  - File operations and editing capabilities
  - Git integration and version control
  - Project understanding and context awareness
  - Tool use and system integration
  - MCP (Model Context Protocol) support
  - Architect mode for complex tasks
  - All CLI commands and options
- **Interactive Session**: Real-time bidirectional communication with Claude Code
- **Working Directory Awareness**: Operates in the correct project context
- **Process Management**: Proper subprocess lifecycle management

### 💻 **Terminal Features**
- Full xterm.js terminal emulation
- Complete keyboard support (arrows, ctrl+c, etc.)
- Colors and syntax highlighting
- Terminal resizing and responsive design
- Copy/paste functionality
- Scrollback buffer

### 📦 **Project Management**
- **Download Button**: One-click project archive creation
- **Smart Exclusions**: Automatically excludes `node_modules`, `.git`, logs, etc.
- **Timestamped Archives**: Generates `project-YYYY-MM-DD.tar.gz` files
- **In-Memory Processing**: Creates archives without temporary files on disk

## Setup

### Prerequisites
- **Deno**: Install from [deno.land](https://deno.land/)
- **Anthropic API Key**: Required for Claude Code functionality

### Installation
```bash
# Navigate to the project directory
cd mods/js-demo

# Install Claude Code package
pnpm install

# Install Claude Code for Deno (enables subprocess execution)
deno install --allow-scripts=npm:@anthropic-ai/claude-code@1.0.21

# Run the server
deno run --allow-net --allow-read --allow-write --allow-env --allow-run index.ts
```

### Configuration
Set your Anthropic API key:
```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

The server will:
- Start on port 8000 (configurable via `PORT` environment variable)
- Spawn Claude Code CLI processes using Deno as the runtime
- Use the current working directory as the project context
- Handle multiple concurrent Claude Code sessions

## Usage

1. **Launch**: Open `http://localhost:8000` in your browser
2. **Connect**: Click the big "PLAY" button to start your neural link
3. **Interact**: Use the terminal exactly like the real Claude Code CLI:
   - All Claude Code commands work (`/help`, `/config`, etc.)
   - File operations and editing
   - Git workflows and project analysis
   - Tool use and system integration
   - MCP server support
4. **Download**: Click the download arrow to get a project archive
5. **Settings**: Use the gear icon to access terminal settings

## Technical Architecture

### Backend (Deno + TypeScript)
- **Subprocess Management**: Spawns real Claude Code CLI processes using Deno
- **Stream Handling**: Bidirectional communication between WebSocket and Claude Code stdio
- **Session Management**: Tracks multiple concurrent Claude Code instances
- **Archive Creation**: On-demand tar.gz generation with smart exclusions
- **Process Lifecycle**: Proper cleanup on disconnect/exit

### Frontend (Vanilla JS + xterm.js)
- **Terminal Emulation**: Full-featured terminal using xterm.js
- **WebSocket Communication**: Real-time bidirectional data flow
- **Sci-Fi UI**: Custom CSS with animations and cyberpunk styling
- **Responsive Design**: Works on desktop and mobile devices

### Claude Code Execution
- **Deno Runtime**: Uses `deno run --allow-all` to execute Claude Code CLI
- **Node.js Compatibility**: Deno runs the Node.js-based Claude Code seamlessly
- **Full Feature Support**: All Claude Code functionality available
- **Container Ready**: Works in Docker without requiring Node.js installation

## Docker Compatibility

This implementation works perfectly in Docker containers because:
- **No Node.js Required**: Uses Deno to run the Claude Code CLI
- **Self-Contained**: All dependencies bundled in node_modules
- **Subprocess Execution**: `deno run` handles the Node.js compatibility layer
- **Full Functionality**: Maintains all Claude Code features in containerized environments

### Docker Usage
```dockerfile
FROM denoland/deno:alpine

WORKDIR /app
COPY . .

# Install dependencies
RUN deno install --allow-scripts=npm:@anthropic-ai/claude-code@1.0.21

# Run the server
CMD ["deno", "run", "--allow-all", "index.ts"]
```

## Advanced Features

- **Real Claude Code**: Uses the actual Anthropic package, not a simulation
- **Multi-Session Support**: Handle multiple concurrent Claude Code instances
- **Process Lifecycle Management**: Proper cleanup on disconnect/exit
- **Error Handling**: Graceful handling of process errors and crashes
- **Stream Processing**: Real-time stdout/stderr handling
- **Signal Management**: Proper SIGTERM handling for clean shutdowns

## Environment Variables

- `PORT`: Server port (default: 8000)
- `ANTHROPIC_API_KEY`: Required by Claude Code CLI
- Any other environment variables used by Claude Code

## Commands

All Claude Code CLI commands are available:
- `/help` - Show Claude Code help
- `/config` - Manage configuration
- `/bug` - Report bugs
- All interactive commands and features

## Benefits

✅ **Real Claude Code**: Uses the actual CLI, not a simulation
✅ **Full Functionality**: All features, tools, and capabilities
✅ **Container Ready**: Works in Docker without Node.js
✅ **Process Management**: Proper subprocess handling
✅ **Interactive**: Real-time bidirectional communication
✅ **Scalable**: Multiple concurrent sessions
✅ **Beautiful UI**: Sci-fi themed terminal interface

This interface provides the complete Claude Code experience in a stunning sci-fi web terminal that works anywhere Deno can run!

## File Structure

```
mods/js-demo/
├── index.html          # Frontend with terminal interface
├── index.ts            # Deno server with Claude integration
├── package.json        # Project metadata
└── README.md          # This file
```

## Customization

### Changing the AI Model
Edit the `model` parameter in `callClaudeAPI()` function:
```typescript
model: "claude-3-5-sonnet-20241022"  # Change to desired model
```

### Modifying the System Prompt
Update the `systemPrompt` variable in the WebSocket handler to customize Claude's behavior.

### Styling Changes
Modify the CSS variables in the `<style>` section of `index.html` to change colors, fonts, or effects.

## Security Notes

- API key is required and should be kept secure
- File downloads are limited to the working directory
- WebSocket connections are session-isolated
- No persistent data storage (conversations are session-only)

## Browser Compatibility

- Modern browsers with WebSocket support
- xterm.js compatibility requirements
- CSS Grid and Flexbox support needed for layout

---

**VIBEZ** - Where neural networks meet retro-futurism. 🚀
