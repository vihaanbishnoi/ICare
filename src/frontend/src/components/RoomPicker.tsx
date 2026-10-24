/** Which room this fixed camera (or the uploaded video's camera) watches. */
import { ROOMS } from '../portal/data';

export function RoomPicker({ value, onChange, disabled }: { value: string; onChange: (room: string) => void; disabled?: boolean }) {
  return <label className="roompick">
    <span>Room</span>
    <select value={value} onChange={event => onChange(event.target.value)} disabled={disabled}
      aria-describedby="roompick-hint">
      <option value="">No room</option>
      {ROOMS.map(room => <option key={room} value={room}>Room {room}</option>)}
    </select>
    <small id="roompick-hint">{value
      ? `Falls found are added to Room ${value}'s danger zone.`
      : 'Without a room, falls still get a clip but do not build a danger zone.'}</small>
  </label>;
}
