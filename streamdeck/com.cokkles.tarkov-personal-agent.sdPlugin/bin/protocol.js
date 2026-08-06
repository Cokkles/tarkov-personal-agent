import crypto from "node:crypto";
import net from "node:net";

export function encodeClientFrame(payload, opcode = 0x1) {
  const data = Buffer.isBuffer(payload) ? payload : Buffer.from(String(payload), "utf8");
  const mask = crypto.randomBytes(4);
  let header;
  if (data.length < 126) {
    header = Buffer.alloc(2);
    header[1] = 0x80 | data.length;
  } else if (data.length <= 0xffff) {
    header = Buffer.alloc(4);
    header[1] = 0x80 | 126;
    header.writeUInt16BE(data.length, 2);
  } else {
    header = Buffer.alloc(10);
    header[1] = 0x80 | 127;
    header.writeBigUInt64BE(BigInt(data.length), 2);
  }
  header[0] = 0x80 | opcode;
  const masked = Buffer.alloc(data.length);
  for (let index = 0; index < data.length; index += 1) {
    masked[index] = data[index] ^ mask[index % 4];
  }
  return Buffer.concat([header, mask, masked]);
}

export function consumeServerFrames(input) {
  let offset = 0;
  const frames = [];
  while (offset + 2 <= input.length) {
    const first = input[offset];
    const second = input[offset + 1];
    const opcode = first & 0x0f;
    const masked = (second & 0x80) !== 0;
    let length = second & 0x7f;
    let cursor = offset + 2;
    if (length === 126) {
      if (cursor + 2 > input.length) break;
      length = input.readUInt16BE(cursor);
      cursor += 2;
    } else if (length === 127) {
      if (cursor + 8 > input.length) break;
      const value = input.readBigUInt64BE(cursor);
      if (value > BigInt(Number.MAX_SAFE_INTEGER)) {
        throw new Error("Stream Deck WebSocket frame is too large");
      }
      length = Number(value);
      cursor += 8;
    }
    let mask;
    if (masked) {
      if (cursor + 4 > input.length) break;
      mask = input.subarray(cursor, cursor + 4);
      cursor += 4;
    }
    if (cursor + length > input.length) break;
    const payload = Buffer.from(input.subarray(cursor, cursor + length));
    if (mask) {
      for (let index = 0; index < payload.length; index += 1) {
        payload[index] ^= mask[index % 4];
      }
    }
    frames.push({ opcode, payload });
    offset = cursor + length;
  }
  return { frames, rest: input.subarray(offset) };
}

export class LocalWebSocketClient {
  constructor(port) {
    this.port = Number(port);
    this.socket = null;
    this.open = false;
    this.handshakeBuffer = Buffer.alloc(0);
    this.frameBuffer = Buffer.alloc(0);
    this.onMessage = () => {};
    this.onClose = () => {};
  }

  connect() {
    return new Promise((resolve, reject) => {
      const key = crypto.randomBytes(16).toString("base64");
      const expectedAccept = crypto
        .createHash("sha1")
        .update(`${key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`)
        .digest("base64");
      const socket = net.createConnection({ host: "127.0.0.1", port: this.port });
      this.socket = socket;
      let settled = false;
      socket.once("connect", () => {
        socket.write(
          [
            "GET / HTTP/1.1",
            `Host: 127.0.0.1:${this.port}`,
            "Upgrade: websocket",
            "Connection: Upgrade",
            `Sec-WebSocket-Key: ${key}`,
            "Sec-WebSocket-Version: 13",
            "",
            "",
          ].join("\r\n"),
        );
      });
      socket.on("data", (chunk) => {
        try {
          if (!this.open) {
            this.handshakeBuffer = Buffer.concat([this.handshakeBuffer, chunk]);
            const boundary = this.handshakeBuffer.indexOf("\r\n\r\n");
            if (boundary === -1) return;
            const headerText = this.handshakeBuffer.subarray(0, boundary).toString("utf8");
            const remaining = this.handshakeBuffer.subarray(boundary + 4);
            const lower = headerText.toLowerCase();
            if (!headerText.startsWith("HTTP/1.1 101")) {
              throw new Error(`Stream Deck WebSocket handshake failed: ${headerText}`);
            }
            if (!lower.includes(`sec-websocket-accept: ${expectedAccept.toLowerCase()}`)) {
              throw new Error("Stream Deck WebSocket handshake signature was invalid");
            }
            this.open = true;
            settled = true;
            resolve();
            if (remaining.length) this._consume(remaining);
            return;
          }
          this._consume(chunk);
        } catch (error) {
          if (!settled) {
            settled = true;
            reject(error);
          }
          socket.destroy(error);
        }
      });
      socket.once("error", (error) => {
        if (!settled) {
          settled = true;
          reject(error);
        }
      });
      socket.once("close", () => {
        this.open = false;
        this.onClose();
      });
    });
  }

  _consume(chunk) {
    this.frameBuffer = Buffer.concat([this.frameBuffer, chunk]);
    const { frames, rest } = consumeServerFrames(this.frameBuffer);
    this.frameBuffer = Buffer.from(rest);
    for (const frame of frames) {
      if (frame.opcode === 0x1) {
        this.onMessage(frame.payload.toString("utf8"));
      } else if (frame.opcode === 0x8) {
        this.close();
      } else if (frame.opcode === 0x9) {
        this._sendFrame(frame.payload, 0xa);
      }
    }
  }

  _sendFrame(payload, opcode = 0x1) {
    if (!this.socket || !this.open) {
      throw new Error("Stream Deck WebSocket is not connected");
    }
    this.socket.write(encodeClientFrame(payload, opcode));
  }

  sendJson(value) {
    this._sendFrame(JSON.stringify(value));
  }

  close() {
    if (this.socket && !this.socket.destroyed) {
      if (this.open) this.socket.write(encodeClientFrame(Buffer.alloc(0), 0x8));
      this.socket.end();
    }
  }
}
