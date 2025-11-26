from badgeware import screen, io, brushes, shapes, run, PixelFont, file_exists
import json
import asyncio
import random

# Note: Bluetooth functionality requires aioble/bluetooth modules
# which are only available on the badge hardware, not in dev environment
try:
    import aioble
    import bluetooth
    BLUETOOTH_AVAILABLE = True
except ImportError:
    BLUETOOTH_AVAILABLE = False

# Bluetooth UUIDs - Custom service for text display
_TEXT_SERVICE_UUID = None
_TEXT_CHAR_UUID = None
_ADV_INTERVAL_US = 250_000

# GATT objects (initialized in init())
text_service = None
text_characteristic = None

if BLUETOOTH_AVAILABLE:
    _TEXT_SERVICE_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef0")
    _TEXT_CHAR_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef1")

# Save file path
_SAVE_FILE = "/badge2_text.json"

# Global state
state = {
    "text": "The quick brown fox jumps",
    "status": "Initializing...",
    "bt_phase": "idle",  # idle, advertising, connected
    "password": "----",
    "advertising": None,  # Temporary handle during advertising
    "connection": None,   # Temporary handle during connection
    "error_text": None,   # Temporary error message to display
    "error_time": 0       # Time when error was shown
}


def load_text():
    """Load saved text from file."""
    try:
        if file_exists(_SAVE_FILE):
            with open(_SAVE_FILE, "r") as f:
                data = json.load(f)
                return data.get("text", state["text"])
    except Exception:
        pass
    return state["text"]


def save_text(text):
    """Save text to file."""
    try:
        with open(_SAVE_FILE, "w") as f:
            json.dump({"text": text}, f)
    except Exception:
        pass


def generate_password():
    """Generate a random 4-character alphanumeric password."""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join(random.choice(chars) for _ in range(4))


def handle_bluetooth():
    """Handle Bluetooth operations synchronously in update loop."""
    if not BLUETOOTH_AVAILABLE:
        return
    
    try:
        if state["bt_phase"] == "idle":
            state["status"] = "Starting..."
            try:
                state["advertising"] = aioble.advertise(
                    _ADV_INTERVAL_US,
                    name="badge2-text",
                    services=[_TEXT_SERVICE_UUID],
                )
                state["bt_phase"] = "advertising"
                state["status"] = "Advertising..."
            except Exception:
                state["status"] = "Adv failed"
                state["bt_phase"] = "error"
                return
            
        elif state["bt_phase"] == "advertising":
            state["status"] = "Waiting..."
            try:
                connection = asyncio.run(state["advertising"])
                state["connection"] = connection
                state["bt_phase"] = "connected"
                state["status"] = "Connected!"
            except Exception:
                state["status"] = "Conn failed"
                state["bt_phase"] = "idle"
                state["advertising"] = None
                return
            
        elif state["bt_phase"] == "connected":
            connection = state["connection"]
            
            if not connection.is_connected():
                state["status"] = "Disconnected"
                state["connection"] = None
                state["advertising"] = None
                state["bt_phase"] = "idle"
                # Clear buffer on disconnect
                if "write_buffer" in state:
                    del state["write_buffer"]
                return
            
            # Initialize buffer if needed
            if "write_buffer" not in state:
                state["write_buffer"] = b""
            
            state["status"] = "Listening..."
            
            try:
                # Wait for write event (returns connection only, not data)
                conn = asyncio.run(
                    asyncio.wait_for(text_characteristic.written(), timeout=2.0)
                )
                
                # Read this fragment from characteristic
                fragment = text_characteristic.read()
                
                if fragment:
                    # Append to buffer
                    state["write_buffer"] += fragment
                    
                    # Try to parse complete JSON
                    try:
                        payload = json.loads(state["write_buffer"].decode('utf-8'))
                        
                        # Success! Clear buffer and process
                        state["write_buffer"] = b""
                        
                        password_key = "password"
                        text_key = "text"
                        
                        # Validate payload structure and password
                        if password_key not in payload or text_key not in payload:
                            state["status"] = "Bad format"
                            state["error_text"] = f"Missing fields: {list(payload.keys())}"
                            state["error_time"] = io.ticks
                            return
                        
                        if payload[password_key] != state["password"]:
                            state["status"] = "Auth failed"
                            return
                        
                        # Update text and characteristic value for reads
                        new_text = payload[text_key]
                        state["text"] = new_text
                        save_text(new_text)
                        
                        # Update the characteristic value so clients can read the new text
                        text_characteristic.write(new_text.encode('utf-8'), send_update=False)
                        
                        state["status"] = "Updated!"
                    
                    except (ValueError, KeyError) as e:
                        # Incomplete JSON - keep buffering, will try again on next fragment
                        # Status already updated above with buffer size
                        
                        # Safety: prevent buffer overflow
                        if len(state["write_buffer"]) > 512:
                            state["status"] = "Buffer overflow"
                            state["error_text"] = f"Exceeded 512 bytes: {state['write_buffer'][:50]}"
                            state["error_time"] = io.ticks
                            state["write_buffer"] = b""
                    
            except asyncio.TimeoutError:
                # Timeout - clear any incomplete data to prevent stale buffer
                if len(state["write_buffer"]) > 0:
                    state["write_buffer"] = b""
                pass
            except Exception as e:
                state["status"] = "Write error"
                state["error_text"] = f"BLE Error: {str(e)}"
                state["error_time"] = io.ticks
                state["write_buffer"] = b""
                
    except Exception:
        state["status"] = "BT Error"
        state["bt_phase"] = "error"
        state["advertising"] = None
        state["connection"] = None


def init():
    """Initialize the app."""
    global state, text_service, text_characteristic
    
    # Load font and enable antialiasing
    screen.font = PixelFont.load("/system/assets/fonts/nope.ppf")
    screen.antialias = screen.X2
    
    # Load saved text
    state["text"] = load_text()
    
    if BLUETOOTH_AVAILABLE:
        try:
            # Generate random password (displayed on screen, not transmitted via BLE)
            state["password"] = generate_password()
            
            # Set up GATT Server
            text_service = aioble.Service(_TEXT_SERVICE_UUID)
            text_characteristic = aioble.Characteristic(
                text_service, _TEXT_CHAR_UUID, write=True, read=True
            )
            
            aioble.register_services(text_service)
            
            # Set initial characteristic value
            text_characteristic.write(state["text"].encode('utf-8'))
            
            state["status"] = "Ready"
            state["bt_phase"] = "idle"
        except Exception:
            state["status"] = "Init failed"
            state["bt_phase"] = "error"
    else:
        state["status"] = "BT unavailable"


def update():
    """Main update loop called every frame."""
    # Handle Bluetooth (this may block during connection/write operations)
    # Only call if not in error state
    if BLUETOOTH_AVAILABLE and state["bt_phase"] != "error":
        handle_bluetooth()
    
    # Clear error text after 3 seconds
    if state["error_text"] and (io.ticks - state["error_time"]) > 3000:
        state["error_text"] = None
    
    # Clear screen with dark blue background
    screen.brush = brushes.color(0, 20, 40)
    screen.clear()
    
    # Draw status bar at top
    screen.brush = brushes.color(100, 150, 200, 128)
    screen.draw(shapes.rectangle(0, 0, 160, 15))
    
    # Draw status text
    screen.brush = brushes.color(255, 255, 255)
    screen.text(state["status"][:25], 5, 3)
    
    # Draw password in top right
    screen.brush = brushes.color(255, 255, 100)
    password_text = f"PW: {state.get('password', '----')}"
    pw_width, _ = screen.measure_text(password_text)
    screen.text(password_text, 160 - pw_width - 5, 18)
    
    # Draw error message if present, otherwise draw main text
    if state["error_text"]:
        screen.brush = brushes.color(255, 100, 100)
        # Word wrap error text
        words = state["error_text"].split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            test_width, _ = screen.measure_text(test_line)
            if test_width > 155:
                if current_line:
                    lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        
        if current_line:
            lines.append(current_line)
        
        # Draw error lines
        start_y = 55 - ((len(lines) - 1) * 8)
        for i, line in enumerate(lines):
            line_width, _ = screen.measure_text(line)
            line_x = max(0, (160 - line_width) // 2)
            screen.text(line, line_x, start_y + i * 16)
    else:
        # Draw main text centered
        screen.brush = brushes.color(255, 255, 255)
        text_width, _ = screen.measure_text(state["text"])
        x = max(0, (160 - text_width) // 2)
        y = 55  # Center vertically
        
        # Word wrap if text is too long
        if text_width > 155:
            words = state["text"].split()
            lines = []
            current_line = ""
            
            for word in words:
                test_line = current_line + (" " if current_line else "") + word
                test_width, _ = screen.measure_text(test_line)
                if test_width > 155:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
                else:
                    current_line = test_line
            
            if current_line:
                lines.append(current_line)
            
            # Draw wrapped lines
            start_y = 55 - ((len(lines) - 1) * 8)
            for i, line in enumerate(lines):
                line_width, _ = screen.measure_text(line)
                line_x = max(0, (160 - line_width) // 2)
                screen.text(line, line_x, start_y + i * 16)
        else:
            screen.text(state["text"], x, y)
    
    # Draw instructions at bottom
    screen.brush = brushes.color(150, 150, 150)
    help_text = "Connect via BLE to update"
    help_width, _ = screen.measure_text(help_text)
    screen.text(help_text, (160 - help_width) // 2, 105)


def on_exit():
    """Cleanup on exit."""
    if BLUETOOTH_AVAILABLE and state.get("connection"):
        try:
            asyncio.run(state["connection"].disconnect())
        except Exception:
            pass


if __name__ == "__main__":
    run(update)
