/* D-LOGG Solar card for Home Assistant Lovelace.
 *
 * Draws a schematic of the solar thermal system: storage tank with its
 * temperature sensors, solar collector with irradiation, the heat generator
 * and two heating circuits, each with flow/return/room temperatures.
 *
 * Usage (YAML):
 *   type: custom:dlogg-solar-card
 *   tank:
 *     top: sensor.tank_1_top
 *     coupling: sensor.tank_1_coupling
 *     reserve: sensor.tank_1_reserve
 *     charging_line: sensor.tank_1_charging_line
 *   solar:
 *     irradiation: sensor.sol_solar_irradiation
 *     tank: sensor.sol_solar_tank_temperature
 *   heat_generator:
 *     flow: sensor.we1_operating_temperature
 *     return: sensor.we1_return_temperature
 *   circuit1:
 *     flow: sensor.wa1_flow_temperature
 *     return: sensor.wa1_return_temperature
 *     room: sensor.wa1_room_temperature
 *   circuit2:
 *     flow: sensor.we2_return_temperature
 *     return: sensor.wa2_room_temperature
 *     room: sensor.wa2_room_temperature
 */

class DloggSolarCard extends HTMLElement {
  setConfig(config) {
    if (!config) throw new Error("Missing card configuration");
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _value(entity) {
    if (!entity || !this._hass) return null;
    const s = this._hass.states[entity];
    if (!s || s.state === "unknown" || s.state === "unavailable") return null;
    const v = parseFloat(s.state);
    return Number.isFinite(v) ? v : null;
  }

  _temp(entity) {
    const v = this._value(entity);
    return v === null ? "—" : v.toFixed(1);
  }

  _watt(entity) {
    const v = this._value(entity);
    return v === null ? "—" : Math.round(v) + " W/m²";
  }

  _color(t) {
    if (t === null) return "#9e9e9e";
    const hue = Math.max(0, Math.min(210, 210 - (Math.max(0, Math.min(60, t)) / 60) * 210));
    return `hsl(${hue}, 80%, 45%)`;
  }

  _dot(cx, cy, t, label, value, anchor) {
    return `<circle cx="${cx}" cy="${cy}" r="5" fill="${this._color(t)}" stroke="#fff" stroke-width="1.5"/>
      <text x="${cx + (anchor === "left" ? -10 : 10)}" y="${cy + 4}" text-anchor="${anchor === "left" ? "end" : "start"}" font-size="11" fill="#ccc">${label}: <tspan fill="${this._color(t)}" font-weight="bold">${value} °C</tspan></text>`;
  }

  _render() {
    const c = this._config || {};
    const tank = c.tank || {};
    const solar = c.solar || {};
    const we = c.heat_generator || {};
    const c1 = c.circuit1 || {};
    const c2 = c.circuit2 || {};

    const tTop = this._value(tank.top);
    const tCoupling = this._value(tank.coupling);
    const tReserve = this._value(tank.reserve);
    const tCharging = this._value(tank.charging_line);
    const tSolarTank = this._value(solar.tank);
    const tWeFlow = this._value(we.flow);
    const tWeReturn = this._value(we.return);
    const tC1Flow = this._value(c1.flow);
    const tC1Return = this._value(c1.return);
    const tC1Room = this._value(c1.room);
    const tC2Flow = this._value(c2.flow);
    const tC2Return = this._value(c2.return);
    const tC2Room = this._value(c2.room);

    this.innerHTML = `
<ha-card header="${c.title || "Solar thermal system"}" style="padding:12px">
<svg viewBox="0 0 480 340" width="100%" style="max-width:520px;display:block;margin:auto;font-family:sans-serif">
  <!-- solar collector -->
  <g>
    <rect x="20" y="24" width="100" height="52" rx="4" fill="#1c1c1c" stroke="#f7b731" stroke-width="2"/>
    <line x1="30" y1="34" x2="110" y2="66" stroke="#f7b731" stroke-width="1" opacity="0.6"/>
    <line x1="30" y1="66" x2="110" y2="34" stroke="#f7b731" stroke-width="1" opacity="0.6"/>
    <text x="70" y="20" text-anchor="middle" font-size="12" fill="#f7b731" font-weight="bold">SOL</text>
    <text x="70" y="94" text-anchor="middle" font-size="11" fill="${this._color(tSolarTank)}">${this._watt(solar.irradiation)}</text>
    <text x="70" y="108" text-anchor="middle" font-size="11" fill="${this._color(tSolarTank)}">tank ${this._temp(solar.tank)} °C</text>
    <line x1="70" y1="76" x2="70" y2="150" stroke="#f7b731" stroke-width="2"/>
    <line x1="70" y1="150" x2="150" y2="150" stroke="#f7b731" stroke-width="2"/>
  </g>

  <!-- storage tank -->
  <g>
    <rect x="150" y="40" width="100" height="230" rx="14" fill="#16324f" stroke="#4aa3df" stroke-width="2"/>
    <text x="200" y="32" text-anchor="middle" font-size="12" fill="#4aa3df" font-weight="bold">STORAGE TANK</text>
    ${this._dot(150, 70, tTop, "top", this._temp(tank.top), "left")}
    ${this._dot(150, 110, tCoupling, "coupling", this._temp(tank.coupling), "left")}
    ${this._dot(150, 150, tReserve, "reserve", this._temp(tank.reserve), "left")}
    ${this._dot(150, 190, tCharging, "charging", this._temp(tank.charging_line), "left")}
    <line x1="250" y1="150" x2="310" y2="150" stroke="#4aa3df" stroke-width="2"/>
  </g>

  <!-- heat generator WE -->
  <g>
    <rect x="310" y="120" width="70" height="60" rx="6" fill="#3a1c1c" stroke="#e74c3c" stroke-width="2"/>
    <text x="345" y="112" text-anchor="middle" font-size="12" fill="#e74c3c" font-weight="bold">WE</text>
    <text x="345" y="145" text-anchor="middle" font-size="11" fill="${this._color(tWeFlow)}">flow ${this._temp(we.flow)} °C</text>
    <text x="345" y="162" text-anchor="middle" font-size="11" fill="${this._color(tWeReturn)}">return ${this._temp(we.return)} °C</text>
    <line x1="380" y1="135" x2="410" y2="135" stroke="#e74c3c" stroke-width="2"/>
    <line x1="380" y1="165" x2="410" y2="165" stroke="#4aa3df" stroke-width="2"/>
  </g>

  <!-- heating circuit 1 -->
  <g>
    <rect x="410" y="100" width="56" height="70" rx="4" fill="#1c1c1c" stroke="#bbb" stroke-width="1.5"/>
    <line x1="418" y1="108" x2="458" y2="162" stroke="#bbb" stroke-width="1"/>
    <line x1="418" y1="162" x2="458" y2="108" stroke="#bbb" stroke-width="1"/>
    <text x="438" y="92" text-anchor="middle" font-size="12" fill="#bbb" font-weight="bold">WA1</text>
    <text x="438" y="186" text-anchor="middle" font-size="10" fill="${this._color(tC1Flow)}">flow ${this._temp(c1.flow)}</text>
    <text x="438" y="199" text-anchor="middle" font-size="10" fill="${this._color(tC1Return)}">return ${this._temp(c1.return)}</text>
    <text x="438" y="212" text-anchor="middle" font-size="10" fill="${this._color(tC1Room)}">room ${this._temp(c1.room)}</text>
  </g>

  <!-- heating circuit 2 -->
  <g>
    <rect x="410" y="220" width="56" height="70" rx="4" fill="#1c1c1c" stroke="#bbb" stroke-width="1.5"/>
    <line x1="418" y1="228" x2="458" y2="282" stroke="#bbb" stroke-width="1"/>
    <line x1="418" y1="282" x2="458" y2="228" stroke="#bbb" stroke-width="1"/>
    <text x="438" y="212" text-anchor="middle" font-size="12" fill="#bbb" font-weight="bold">WA2</text>
    <text x="438" y="306" text-anchor="middle" font-size="10" fill="${this._color(tC2Flow)}">flow ${this._temp(c2.flow)}</text>
    <text x="438" y="319" text-anchor="middle" font-size="10" fill="${this._color(tC2Return)}">return ${this._temp(c2.return)}</text>
    <text x="438" y="332" text-anchor="middle" font-size="10" fill="${this._color(tC2Room)}">room ${this._temp(c2.room)}</text>
  </g>
</svg>
</ha-card>`;
  }
}

customElements.define("dlogg-solar-card", DloggSolarCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "dlogg-solar-card",
  name: "D-LOGG Solar card",
  description: "Schematic of storage tank, solar, heat generator and two heating circuits with live temperatures.",
});
