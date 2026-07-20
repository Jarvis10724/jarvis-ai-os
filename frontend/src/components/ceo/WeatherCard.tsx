import { useEffect, useState } from "react";
import { Cloud, CloudRain, CloudSnow, Sun, CloudSun, Zap, CloudFog } from "lucide-react";

// Sacramento, CA 95842 (North Highlands) — hardcoded since there's no
// per-user location setting yet. Open-Meteo needs no API key and allows
// browser CORS, so this fetches directly rather than proxying through the
// backend.
const LAT = 38.6857;
const LON = -121.3616;

// WMO weather codes (https://open-meteo.com/en/docs) collapsed into the
// handful of buckets we actually render.
function describeCode(code: number): { label: string; Icon: typeof Sun } {
  if (code === 0) return { label: "Clear", Icon: Sun };
  if ([1, 2].includes(code)) return { label: "Partly cloudy", Icon: CloudSun };
  if (code === 3) return { label: "Overcast", Icon: Cloud };
  if ([45, 48].includes(code)) return { label: "Fog", Icon: CloudFog };
  if ([51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82].includes(code)) return { label: "Rain", Icon: CloudRain };
  if ([71, 73, 75, 77, 85, 86].includes(code)) return { label: "Snow", Icon: CloudSnow };
  if ([95, 96, 99].includes(code)) return { label: "Thunderstorms", Icon: Zap };
  return { label: "—", Icon: Cloud };
}

interface WeatherState {
  tempF: number;
  feelsLikeF: number;
  code: number;
  highF: number;
  lowF: number;
}

export default function WeatherCard() {
  const [weather, setWeather] = useState<WeatherState | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const url =
          `https://api.open-meteo.com/v1/forecast?latitude=${LAT}&longitude=${LON}` +
          "&current=temperature_2m,apparent_temperature,weather_code" +
          "&daily=temperature_2m_max,temperature_2m_min" +
          "&temperature_unit=fahrenheit&timezone=America%2FLos_Angeles&forecast_days=1";
        const resp = await fetch(url);
        if (!resp.ok) throw new Error("weather fetch failed");
        const data = await resp.json();
        if (!cancelled) {
          setWeather({
            tempF: Math.round(data.current.temperature_2m),
            feelsLikeF: Math.round(data.current.apparent_temperature),
            code: data.current.weather_code,
            highF: Math.round(data.daily.temperature_2m_max[0]),
            lowF: Math.round(data.daily.temperature_2m_min[0]),
          });
        }
      } catch {
        if (!cancelled) setError(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const { label, Icon } = weather ? describeCode(weather.code) : { label: "", Icon: Cloud };

  return (
    <div className="hud-panel hud-corner flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-jarvis-border/60 px-5 py-4">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-jarvis-cyan" />
          <h2 className="font-display text-sm font-semibold tracking-widest text-jarvis-text">WEATHER</h2>
        </div>
        <span className="text-xs text-jarvis-muted">Sacramento, CA</span>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center gap-1 p-4">
        {error ? (
          <p className="text-xs text-jarvis-muted">Couldn't load weather right now.</p>
        ) : !weather ? (
          <div className="h-8 w-16 animate-pulse rounded bg-jarvis-panel2/60" />
        ) : (
          <>
            <p className="font-data text-3xl font-bold text-jarvis-text">{weather.tempF}°F</p>
            <p className="text-xs text-jarvis-muted">
              {label} · Feels like {weather.feelsLikeF}°
            </p>
            <p className="mt-1 font-data text-xs text-jarvis-muted">
              H {weather.highF}° · L {weather.lowF}°
            </p>
          </>
        )}
      </div>
    </div>
  );
}
