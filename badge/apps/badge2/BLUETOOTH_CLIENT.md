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

**Password Authentication:**
The badge generates a random 4-character alphanumeric password on boot. This password must be included with all text write operations. The password is **only displayed on the badge screen** and is **NOT transmitted via Bluetooth**. Users must have physical access to the badge to read the password.

**Password Format:**
- Exactly 4 alphanumeric characters (e.g., "A7K2", "Q3M9")
- Generated randomly on badge boot/reset
- **Only visible on badge screen** - not available via Bluetooth characteristic
- Proves physical possession of the badge
- Prevents casual trolling at conferences, not designed for strong security

## Connection Process

1. **Obtain Password**: Read the 4-character password from the badge screen (physical access required)

2. **Discovery**: Scan for BLE devices advertising the name `"badge2-text"`

3. **Connect**: Establish a connection to the device

4. **Service Discovery**: Discover the text service using UUID `12345678-1234-5678-1234-56789abcdef0`

5. **Characteristic Discovery**: Find the text characteristic using UUID `12345678-1234-5678-1234-56789abcdef1`

## Reading Current Text

To read the currently displayed text:

```python
# Read the characteristic value
data = await text_characteristic.read()
current_text = data.decode('utf-8')
print(f"Current text: {current_text}")
```

## Writing New Text

All text writes must include the 4-character password that is displayed on the badge screen:

```python
import json

# Password must be obtained by reading the badge screen
# It is NOT available via Bluetooth - this proves physical possession
badge_password = "A7K2"  # Example - read this from the badge screen

# Prepare authenticated payload
payload = {
    "password": badge_password,
    "text": "Hello from my device!"
}

# Encode as JSON and write
data = json.dumps(payload).encode('utf-8')
await text_characteristic.write(data)
```

**Authentication Rules:**
- All writes must be JSON with `password` and `text` fields
- Password is compared as plain text (case-sensitive)
- If password doesn't match, write is rejected silently
- No attempt limiting - incorrect password just fails the write

**Text Constraints:**
- Encoding: UTF-8
- Max recommended length: ~50 characters (for single line display)
- Longer text will be word-wrapped automatically
- No strict limit, but very long text may be truncated or difficult to read

**BLE Packet Fragmentation:**
The badge automatically handles BLE write fragmentation (MTU limitations). The characteristic uses `capture=True` which means:
- **Single writes only** - Each JSON payload should be sent as a single `write()` call
- **Automatic chunking** - The BLE stack automatically fragments large writes into MTU-sized packets
- **Transparent buffering** - The badge buffers incoming fragments and parses when complete JSON is received
- **Status feedback** - Badge displays `"Buffering (Xb)..."` while accumulating fragments
- **No manual chunking needed** - Clients should NOT manually split the JSON payload
- **Max payload size** - 512 bytes (enforced buffer limit for safety)

Most BLE stacks handle this transparently - just write the full JSON payload in one call and the stack will handle packet-level fragmentation based on the negotiated MTU.

## Example Client Code (Python with aioble)

```python
import asyncio
import aioble
import bluetooth
import json

# Service and characteristic UUIDs
TEXT_SERVICE_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef0")
TEXT_CHAR_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef1")
PASSWORD_CHAR_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdef2")

async def update_badge_text(new_text, password):
    """Connect to badge and update text with authentication.
    
    Args:
        new_text: The text to display on the badge
        password: 4-character password read from the badge screen
    """
    
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
                    text_char = await service.characteristic(TEXT_CHAR_UUID)
                    
                    # Read current text
                    current_data = await text_char.read()
                    current_text = current_data.decode('utf-8')
                    print(f"Current text: {current_text}")
                    
                    # Prepare authenticated write with user-provided password
                    payload = {
                        "password": password,
                        "text": new_text
                    }
                    new_data = json.dumps(payload).encode('utf-8')
                    
                    # Write new text
                    await text_char.write(new_data)
                    print(f"Updated text to: {new_text}")
                    
                    # Disconnect
                    await connection.disconnect()
                    return True
                    
                except Exception as e:
                    print(f"Error: {e}")
                    return False
    
    print("Badge not found")
    return False

# Usage - password must be read from badge screen
badge_password = input("Enter 4-character password from badge screen: ")
asyncio.run(update_badge_text("Hello Universe 2025!", password=badge_password))
```

## Example Client Code (Web Bluetooth API)

```javascript
async function updateBadgeText(newText, password) {
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
        
        // Get text characteristic
        const textCharacteristic = await service.getCharacteristic(
            '12345678-1234-5678-1234-56789abcdef1'
        );
        
        // Read current text
        const currentValue = await textCharacteristic.readValue();
        const currentText = new TextDecoder().decode(currentValue);
        console.log('Current text:', currentText);
        
        // Prepare authenticated write with user-provided password
        const payload = {
            password: password,
            text: newText
        };
        const encoder = new TextEncoder();
        const data = encoder.encode(JSON.stringify(payload));
        
        // Write new text in a single call
        // Use writeValueWithResponse for reliability - the BLE stack will handle fragmentation
        await textCharacteristic.writeValueWithResponse(data);
        console.log('Text updated to:', newText);
        
        // Disconnect
        device.gatt.disconnect();
        
    } catch (error) {
        console.error('Error:', error);
    }
}

// Usage - password must be provided (from QR code URL param or user input)
const urlParams = new URLSearchParams(window.location.search);
const password = urlParams.get('password') || prompt('Enter badge password:');
updateBadgeText("Hello from the web!", password);
```

## QR Code Integration

The badge displays its 4-character password on screen along with a QR code:

```
https://yourdomain.com/badge-plus-plus?password=A7K2
```

**QR Code Workflow:**
1. Badge generates random 4-character password on boot (e.g., "A7K2")
2. Badge displays password and QR code on screen (password is NOT transmitted via Bluetooth)
3. User scans QR code with phone (password embedded in URL)
4. Browser opens Badge++ page with password pre-filled in URL parameter
5. User clicks "Connect Badge" button (required by Web Bluetooth security)
6. Client connects via Bluetooth and sends password in write payload
7. Badge validates password matches screen display before accepting text update
8. Password persists until badge is power-cycled/reset

**URL Parameter Format:**
```
/badge-plus-plus?password=A7K2
```

**Benefits:**
- Simple 4-character password easy to read and type manually if needed
- QR code eliminates manual entry
- **Physical access to badge screen required** - password never transmitted via Bluetooth
- Proves user has physical possession of the badge
- Prevents casual conference trolling without complex security
- Password visible on badge so owner can share access intentionally

## Status Display

The badge displays connection status at the top of the screen:

- **"Ready"**: Initialized and ready to start
- **"Starting..."**: Initializing Bluetooth advertising
- **"Advertising..."**: Ready for connections, discoverable as "badge2-text"
- **"Waiting for conn..."**: Blocking, waiting for a device to connect
- **"Connected!"**: Client successfully connected
- **"Listening..."**: Waiting for data writes (2 second timeout loop)
- **"Buffering (Xb)..."**: Receiving fragmented BLE packets (X = bytes buffered so far)
- **"Updated!"**: New text was successfully received and saved
- **"Auth failed"**: Write rejected due to incorrect password
- **"Bad format"**: JSON missing required fields (password/text)
- **"Bad payload"**: JSON parsing or structure error
- **"Buffer overflow"**: Write exceeded 512 byte safety limit
- **"Disconnected"**: Client disconnected, will restart advertising
- **"Write error"**: Error receiving data from client
- **"BT Error"**: Bluetooth error occurred, will retry from idle state

**Password Display:**
- 4-character password displayed prominently on screen
- QR code shown for quick mobile access

## Persistence

- Text is automatically saved to `/badge2_text.json` on the device
- Text is loaded when the app starts
- Default text: "The quick brown fox jumps"
- Password is regenerated on each boot (not persisted, not transmitted via Bluetooth)

## Limitations & Notes

1. **Single Connection**: The badge accepts one connection at a time
2. **Simple Authentication**: 4-character password prevents casual trolling, not designed for strong security
3. **Text Encoding**: Must be valid UTF-8
4. **Display Wrapping**: Text longer than screen width is automatically word-wrapped
5. **Blocking Operations**: Display updates pause during connection establishment and data transfers
6. **Write Timeout**: 2 second timeout when listening for writes (to keep display responsive)
7. **Auto-Reconnect**: Automatically returns to advertising after disconnection
8. **Password on Boot**: New password generated each time badge boots/resets
9. **Physical Access Required**: Password only visible on badge screen, not transmitted via Bluetooth
10. **JSON Payload**: All writes must use JSON format with password and text fields

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
- If password is set, ensure JSON payload includes correct password
- Check status for "Auth failed" message indicating wrong password
- Some platforms require pairing even though the badge doesn't enforce it
- Keep payload under 512 bytes (status shows "Buffer overflow" if exceeded)
- Send entire JSON payload in a single `write()` call (don't manually chunk)

**Badge shows "Buffering (Xb)..." for extended period:**
- Normal behavior for larger payloads being fragmented by BLE stack
- Typical MTU is 20-23 bytes, so a 36-byte JSON takes 2-3 packets
- If stuck buffering, the last packet may have been lost - disconnect and retry
- Check for valid JSON format - incomplete JSON will continue buffering

**Authentication errors:**
- Badge shows "Auth failed" when password is incorrect
- Write silently fails with wrong password (no disconnect)
- Password must be read from badge screen - it is NOT available via Bluetooth
- Ensure JSON payload format is correct: `{"password": "A7K2", "text": "Hello"}`
- Password is case-sensitive
- Scan QR code or manually type password displayed on badge screen

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
1. `init()` generates random 4-character password, sets up GATT service with text characteristic only
2. Displays password and QR code on screen (password NOT exposed via Bluetooth)
3. `update()` calls `handle_bluetooth()` every frame
4. On `idle`: Starts advertising via `aioble.advertise()`
5. On `advertising`: Blocks waiting for connection (display pauses)
6. On `connected`: Polls for writes with 2-second timeout, then continues
7. On write: 
   - Accumulates data in write buffer (handles BLE packet fragmentation)
   - Attempts to parse buffer as JSON after each fragment
   - If incomplete JSON: continues buffering, shows "Buffering (Xb)..." status
   - If complete JSON: validates password field matches screen-displayed password
   - If valid: extracts text, updates display, saves to file, clears buffer
   - If invalid: shows "Auth failed" status, clears buffer, continues listening
   - Safety: clears buffer if it exceeds 512 bytes
8. On disconnect/error: Returns to `idle` and restarts

**Performance Considerations:**
- Display updates pause during connection establishment (typically < 1 second)
- 2-second timeout keeps the listening loop responsive
- Text saves are synchronous but fast (JSON write)
- State updates are immediate and visible in next frame after timeout

## Security Considerations

**Authentication Model:**
- Simple 4-character password prevents casual conference trolling
- Password generated randomly on boot, not user-settable
- **Password ONLY visible on badge screen** - NOT transmitted via Bluetooth
- Plain text passwords sent in JSON payload from client to badge
- Requires physical access to badge to read password
- No attempt limiting or brute force protection

**Threat Model:**
- **Target**: Prevent random conference attendees from trolling badge displays without physical access
- **Casual Tampering**: ✓✓ Mitigated - requires physical access to read password from screen
- **Remote Attacker**: ✓ Mitigated - cannot obtain password without seeing badge screen
- **Determined Attacker with Physical Access**: ✗ Not mitigated - password visible on screen
- **BLE Sniffing**: ⚠️ Partially mitigated - password sent in payload, but only after physical access
- **Brute Force**: ✗ Not mitigated - no attempt limiting (could try all 456,976 combos in ~1 hour if connected)

**Intended Use:**
- Conference badges where casual trolling prevention is desired
- Proof of physical possession model (like Bluetooth pairing)
- Fun personal projects where security isn't critical
- Demonstrations where physical access control exists
- **Not suitable for**: Sensitive data, financial info, authentication tokens

**Design Philosophy:**
- Physical access proves authorization (like unlocking a phone to pair Bluetooth)
- Simplicity over strong security
- Easy to share access (show screen, scan QR, or read 4 chars)
- No lockout risk (password resets on boot)
- Transparent operation (password always visible to badge owner)

**QR Code Security:**
- Password embedded in URL visible to anyone who sees QR code or screen
- **Scanning QR code proves physical access to badge**
- Physical security of badge controls access
- Anyone with camera access to badge can gain control
- Password never transmitted over Bluetooth - only in QR code and on screen
- Acceptable for conference/demo use cases
