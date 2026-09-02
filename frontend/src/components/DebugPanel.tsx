/** Debug panel for Crimson Atlas.
 *
 * Shows WebSocket state, packet stats, render FPS, and coordinate readouts.
 */

interface DebugPanelProps {
  wsState: string;
  lastPacketAge: number;
  packetsPerSec: number;
  renderFps: number;
  absoluteX: number;
  absoluteY: number;
  absoluteZ: number;
  localX: number;
  localY: number;
  localZ: number;
  offsetX: number;
  offsetZ: number;
  mapX: number;
  mapY: number;
  followState: boolean;
  cursorX?: number;
  cursorY?: number;
}

export default function DebugPanel({
  wsState,
  lastPacketAge,
  packetsPerSec,
  renderFps,
  absoluteX,
  absoluteY,
  absoluteZ,
  localX,
  localY,
  localZ,
  offsetX,
  offsetZ,
  mapX,
  mapY,
  followState,
  cursorX,
  cursorY,
}: DebugPanelProps) {
  return (
    <div className="debug-panel">
      <div className="debug-section">
        <div className="debug-title">Connection</div>
        <div>WebSocket: {wsState}</div>
        <div>Last packet: {lastPacketAge.toFixed(1)}s ago</div>
        <div>Packets/sec: {packetsPerSec.toFixed(1)}</div>
        <div>Render FPS: {renderFps.toFixed(1)}</div>
      </div>
      <div className="debug-section">
        <div className="debug-title">Absolute Position</div>
        <div>X: {absoluteX.toFixed(2)}</div>
        <div>Y: {absoluteY.toFixed(2)}</div>
        <div>Z: {absoluteZ.toFixed(2)}</div>
      </div>
      <div className="debug-section">
        <div className="debug-title">Local Position</div>
        <div>X: {localX.toFixed(2)}</div>
        <div>Y: {localY.toFixed(2)}</div>
        <div>Z: {localZ.toFixed(2)}</div>
      </div>
      <div className="debug-section">
        <div className="debug-title">World Offset</div>
        <div>X: {offsetX.toFixed(2)}</div>
        <div>Z: {offsetZ.toFixed(2)}</div>
      </div>
      <div className="debug-section">
        <div className="debug-title">Map Position</div>
        <div>X: {mapX.toFixed(2)}</div>
        <div>Y: {mapY.toFixed(2)}</div>
      </div>
      {cursorX !== undefined && cursorY !== undefined && (
        <div className="debug-section">
          <div className="debug-title">Cursor</div>
          <div>X: {cursorX.toFixed(2)}</div>
          <div>Y: {cursorY.toFixed(2)}</div>
        </div>
      )}
      <div className="debug-section">
        <div className="debug-title">Follow</div>
        <div>{followState ? "ON" : "OFF"}</div>
      </div>
    </div>
  );
}
