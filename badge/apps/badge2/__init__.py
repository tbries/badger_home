from badgeware import screen, io, brushes, shapes, run, PixelFont, file_exists
import json
import asyncio

# Note: Bluetooth functionality requires aioble/bluetooth modules
# which are only available on the badge hardware, not in dev environment
try:
    import aioble
    import bluetooth
    BLUETOOTH_AVAILABLE = True
except ImportError:
    BLUETOOTH_AVAILABLE = False
    print("Bluetooth not available - running in limited mode")

# Bluetooth UUIDs - Custom service for text display
if BLUETOOTH_AVAILABLE:
    _TEXT_SERVICE_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef0")
    _TEXT_CHAR_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef1")
    
    # Advertising interval (250ms)
    _ADV_INTERVAL_US = 250_000
    
    # GATT Server setup
    text_service = aioble.Service(_TEXT_SERVICE_UUID)
    text_characteristic = aioble.Characteristic(
        text_service, _TEXT_CHAR_UUID, write=True, read=True, capture=True
    )
    aioble.register_services(text_service)

# Save file path
_SAVE_FILE = "/badge2_text.json"

# Global state
state = {
    "text": "The quick brown fox jumps",
    "connection_status": "Initializing...",
    "advertising": None,
    "connection": None,
    "bt_phase": "idle"  # idle, advertising, connected
}


def load_text():
    """Load saved text from file."""
    try:
        if file_exists(_SAVE_FILE):
            with open(_SAVE_FILE, "r") as f:
                data = json.load(f)
                return data.get("text", state["text"])
    except Exception as e:
        print(f"Error loading text: {e}")
    return state["text"]


def save_text(text):
    """Save text to file."""
    try:
        with open(_SAVE_FILE, "w") as f:
            json.dump({"text": text}, f)
        print(f"Saved text: {text}")
    except Exception as e:
        print(f"Error saving text: {e}")


def handle_bluetooth():
    """Handle Bluetooth operations synchronously in update loop."""
    if not BLUETOOTH_AVAILABLE:
        return
    
    try:
        if state["bt_phase"] == "idle":
            # Start advertising
            state["connection_status"] = "Starting..."
            print("Starting Bluetooth advertising")
            state["advertising"] = aioble.advertise(
                _ADV_INTERVAL_US,
                name="badge2-text",
                services=[_TEXT_SERVICE_UUID],
            )
            state["bt_phase"] = "advertising"
            state["connection_status"] = "Advertising..."
            print("Now advertising")
            
        elif state["bt_phase"] == "advertising":
            # Check for incoming connection (this will block until connection)
            state["connection_status"] = "Waiting for conn..."
            print("Waiting for connection...")
            
            # This blocks, which is OK per requirements
            connection = asyncio.run(state["advertising"])
            
            state["connection"] = connection
            state["bt_phase"] = "connected"
            state["connection_status"] = "Connected!"
            print(f"Connected: {connection.device}")
            
        elif state["bt_phase"] == "connected":
            # Listen for writes
            connection = state["connection"]
            
            if not connection.is_connected():
                print("Disconnected")
                state["connection_status"] = "Disconnected"
                state["connection"] = None
                state["advertising"] = None
                state["bt_phase"] = "idle"
                return
            
            state["connection_status"] = "Listening..."
            
            try:
                # Wait for write (blocks until write or timeout)
                conn, data = asyncio.run(
                    asyncio.wait_for(text_characteristic.written(), timeout=2.0)
                )
                
                if data:
                    # Decode and save new text
                    new_text = data.decode('utf-8')
                    print(f"Received: {new_text}")
                    state["text"] = new_text
                    save_text(new_text)
                    state["connection_status"] = "Updated!"
                    
                    # Update characteristic for reads
                    text_characteristic.write(data)
                    
            except asyncio.TimeoutError:
                # No write received, continue
                pass
            except Exception as e:
                print(f"Write error: {e}")
                state["connection_status"] = "Write error"
                
    except Exception as e:
        print(f"Bluetooth error: {e}")
        state["connection_status"] = f"BT Error"
        state["bt_phase"] = "idle"
        state["advertising"] = None
        state["connection"] = None


def init():
    """Initialize the app."""
    global state
    
    # Load font and enable antialiasing
    screen.font = PixelFont.load("/system/assets/fonts/nope.ppf")
    screen.antialias = screen.X2
    
    # Load saved text
    state["text"] = load_text()
    
    if BLUETOOTH_AVAILABLE:
        # Set initial characteristic value
        text_characteristic.write(state["text"].encode('utf-8'))
        state["connection_status"] = "Ready"
        state["bt_phase"] = "idle"
        print("Bluetooth initialized")
    else:
        state["connection_status"] = "BT unavailable"


def update():
    """Main update loop called every frame."""
    # Handle Bluetooth (this may block during connection/write operations)
    if BLUETOOTH_AVAILABLE:
        handle_bluetooth()
    
    # Clear screen with dark blue background
    screen.brush = brushes.color(0, 20, 40)
    screen.clear()
    
    # Draw status bar at top
    screen.brush = brushes.color(100, 150, 200, 128)
    screen.draw(shapes.rectangle(0, 0, 160, 15))
    
    # Draw status text
    screen.brush = brushes.color(255, 255, 255)
    status_text = state["connection_status"][:25]
    screen.text(status_text, 5, 3)
    
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
    if BLUETOOTH_AVAILABLE:
        try:
            # Disconnect if connected
            if state.get("connection"):
                asyncio.run(state["connection"].disconnect())
        except:
            pass


if __name__ == "__main__":
    run(update)
