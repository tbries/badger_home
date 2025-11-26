# Badge2 Bluetooth Client Documentation

## Overview

The Badge2 app is a Bluetooth LE peripheral that allows remote devices to update the displayed text. The text is persistently stored and will be restored when the app is relaunched.

**Technical Note**: The app uses MicroPython's `aioble` library for Bluetooth operations. Bluetooth operations run synchronously in the main update loop using `asyncio.run()`, so the display may pause briefly during connection establishment and data transfers.

## Architecture

The app uses a simple state machine in the `update()` loop:
1. **idle** → Starts advertising the device via Bluetooth LE
2. **advertising** → Blocks waiting for incoming connection
3. **connected** → Listens for writes to the text characteristic (2 second timeout)
4. Updates the display and saves text when new data is received
5. Automatically returns to idle state after disconnection or errors

## Bluetooth Service Details

### Service UUID
```
12345678-1234-5678-1234-56789abcdef0
```

### Characteristic UUID (Text)
```
12345678-1234-5678-1234-56789abcdef1
```

**Properties:**
- Read: Yes
- Write: Yes
- Notify: No

## Connection Process

1. **Discovery**: Scan for BLE devices advertising the name `"badge2-text"`

2. **Connect**: Establish a connection to the device

3. **Service Discovery**: Discover the text service using UUID `12345678-1234-5678-1234-56789abcdef0`

4. **Characteristic Discovery**: Find the text characteristic using UUID `12345678-1234-5678-1234-56789abcdef1`

## Reading Current Text

To read the currently displayed text:

```python
# Read the characteristic value
data = await text_characteristic.read()
current_text = data.decode('utf-8')
print(f"Current text: {current_text}")
```

## Writing New Text

To update the displayed text:

```python
# Encode your new text as UTF-8 bytes
new_text = "Hello from my device!"
data = new_text.encode('utf-8')

# Write to the characteristic
await text_characteristic.write(data)
```

**Text Constraints:**
- Encoding: UTF-8
- Max recommended length: ~50 characters (for single line display)
- Longer text will be word-wrapped automatically
- No strict limit, but very long text may be truncated or difficult to read

## Example Client Code (Python with aioble)

```python
import asyncio
import aioble
import bluetooth

# Service and characteristic UUIDs
TEXT_SERVICE_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef0")
TEXT_CHAR_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef1")

async def update_badge_text(new_text):
    """Connect to badge and update text."""
    
    # Scan for the badge
    print("Scanning for badge2-text...")
    async with aioble.scan(duration_ms=5000, active=True) as scanner:
        async for result in scanner:
            if result.name() == "badge2-text":
                print(f"Found badge: {result.device}")
                
                # Connect to the device
                try:
                    connection = await result.device.connect(timeout_ms=5000)
                    print("Connected!")
                    
                    # Discover the text service
                    service = await connection.service(TEXT_SERVICE_UUID)
                    
                    # Get the text characteristic
                    char = await service.characteristic(TEXT_CHAR_UUID)
                    
                    # Read current text
                    current_data = await char.read()
                    current_text = current_data.decode('utf-8')
                    print(f"Current text: {current_text}")
                    
                    # Write new text
                    new_data = new_text.encode('utf-8')
                    await char.write(new_data)
                    print(f"Updated text to: {new_text}")
                    
                    # Disconnect
                    await connection.disconnect()
                    return True
                    
                except Exception as e:
                    print(f"Error: {e}")
                    return False
    
    print("Badge not found")
    return False

# Usage
asyncio.run(update_badge_text("Hello Universe 2025!"))
```

## Example Client Code (Web Bluetooth API)

```javascript
async function updateBadgeText(newText) {
    try {
        // Request device
        const device = await navigator.bluetooth.requestDevice({
            filters: [{ name: 'badge2-text' }],
            optionalServices: ['12345678-1234-5678-1234-56789abcdef0']
        });
        
        // Connect to GATT server
        const server = await device.gatt.connect();
        console.log('Connected!');
        
        // Get service
        const service = await server.getPrimaryService(
            '12345678-1234-5678-1234-56789abcdef0'
        );
        
        // Get characteristic
        const characteristic = await service.getCharacteristic(
            '12345678-1234-5678-1234-56789abcdef1'
        );
        
        // Read current text
        const currentValue = await characteristic.readValue();
        const currentText = new TextDecoder().decode(currentValue);
        console.log('Current text:', currentText);
        
        // Write new text
        const encoder = new TextEncoder();
        const data = encoder.encode(newText);
        await characteristic.writeValue(data);
        console.log('Text updated to:', newText);
        
        // Disconnect
        device.gatt.disconnect();
        
    } catch (error) {
        console.error('Error:', error);
    }
}

// Usage
updateBadgeText("Hello from the web!");
```

## Status Display

The badge displays connection status at the top of the screen:

- **"Ready"**: Initialized and ready to start
- **"Starting..."**: Initializing Bluetooth advertising
- **"Advertising..."**: Ready for connections, discoverable as "badge2-text"
- **"Waiting for conn..."**: Blocking, waiting for a device to connect
- **"Connected!"**: Client successfully connected
- **"Listening..."**: Waiting for data writes (2 second timeout loop)
- **"Updated!"**: New text was successfully received and saved
- **"Disconnected"**: Client disconnected, will restart advertising
- **"Write error"**: Error receiving data from client
- **"BT Error"**: Bluetooth error occurred, will retry from idle state

## Persistence

- Text is automatically saved to `/badge2_text.json` on the device
- The saved text is loaded when the app starts
- Default text: "The quick brown fox jumps"

## Limitations & Notes

1. **Single Connection**: The badge accepts one connection at a time
2. **No Authentication**: No pairing or encryption required (for simplicity)
3. **Text Encoding**: Must be valid UTF-8
4. **Display Wrapping**: Text longer than screen width is automatically word-wrapped
5. **Blocking Operations**: Display updates pause during connection establishment and data transfers
6. **Write Timeout**: 2 second timeout when listening for writes (to keep display responsive)
7. **Auto-Reconnect**: Automatically returns to advertising after disconnection

## Troubleshooting

**Badge not found during scan:**
- Ensure the badge2 app is running (you should see "Advertising..." in the status bar)
- Check that Bluetooth is enabled on your device
- Move closer to the badge (BLE range is typically 10-30 feet)
- The badge must have Bluetooth modules available (hardware requirement)

**Status shows "BT unavailable":**
- The badge hardware doesn't have Bluetooth modules loaded
- This is expected in development/simulation environments

**Status shows "BT Error":**
- There was an exception in the Bluetooth code
- Check the badge console for error details
- Try restarting the app

**Write fails:**
- Ensure data is properly UTF-8 encoded
- Check that the connection is still active
- Verify you're writing to the correct characteristic UUID
- Some platforms require pairing even though the badge doesn't enforce it

**Text not persisting:**
- Check that the device has sufficient storage space
- Ensure the app exits cleanly (not force-killed)
- The save file is `/badge2_text.json` in the root filesystem

**Connection drops frequently:**
- Move closer to the badge
- Reduce interference from other Bluetooth devices
- Some platforms have more stable BLE stacks than others

## Technical Details

**State Machine Implementation:**
The app uses a simple state machine (`bt_phase`) with three states:
- `idle`: Ready to start advertising
- `advertising`: Currently advertising and waiting for connection
- `connected`: Client connected, listening for writes

**Synchronous Bluetooth Operations:**
All async operations are executed synchronously using `asyncio.run()`:
- `asyncio.run(state["advertising"])` - Blocks until connection established
- `asyncio.run(asyncio.wait_for(text_characteristic.written(), timeout=2.0))` - Blocks up to 2 seconds waiting for writes

**Connection Flow:**
1. `init()` sets up GATT service and initializes state to `idle`
2. `update()` calls `handle_bluetooth()` every frame
3. On `idle`: Starts advertising via `aioble.advertise()`
4. On `advertising`: Blocks waiting for connection (display pauses)
5. On `connected`: Polls for writes with 2-second timeout, then continues
6. On write: Decodes data, updates state, saves to file, updates characteristic
7. On disconnect/error: Returns to `idle` and restarts

**Performance Considerations:**
- Display updates pause during connection establishment (typically < 1 second)
- 2-second timeout keeps the listening loop responsive
- Text saves are synchronous but fast (JSON write)
- State updates are immediate and visible in next frame after timeout

## Security Considerations

This implementation prioritizes simplicity over security:

- No authentication required
- No encryption enforced
- Any nearby device can modify the text
- For production use, consider implementing:
  - Pairing/bonding
  - PIN/password protection
  - Encryption
  - Access control lists
