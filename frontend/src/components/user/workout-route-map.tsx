import { useMemo } from 'react';

/**
 * Renders a GPS route (Google Encoded Polyline, precision 5 — e.g. Strava's
 * map.summary_polyline) as a standalone SVG trace. No map tiles or external
 * services: the route is projected onto a plane (with cosine longitude
 * correction so shapes aren't distorted) and fitted to the container.
 */

interface LatLng {
  lat: number;
  lng: number;
}

/** Decodes a Google Encoded Polyline string into lat/lng points. */
function decodePolyline(encoded: string, precision = 5): LatLng[] {
  const factor = 10 ** precision;
  const points: LatLng[] = [];
  let index = 0;
  let lat = 0;
  let lng = 0;

  while (index < encoded.length) {
    for (const axis of ['lat', 'lng'] as const) {
      let shift = 0;
      let result = 0;
      let byte: number;
      do {
        byte = encoded.charCodeAt(index++) - 63;
        result |= (byte & 0x1f) << shift;
        shift += 5;
      } while (byte >= 0x20);
      const delta = result & 1 ? ~(result >> 1) : result >> 1;
      if (axis === 'lat') lat += delta;
      else lng += delta;
    }
    points.push({ lat: lat / factor, lng: lng / factor });
  }

  return points;
}

const VIEW_W = 400;
const VIEW_H = 180;
const PADDING = 14;

export function WorkoutRouteMap({
  polyline,
  className,
}: {
  polyline: string;
  className?: string;
}) {
  const { path, start, end, pointCount } = useMemo(() => {
    const points = decodePolyline(polyline);
    if (points.length < 2) {
      return { path: null, start: null, end: null, pointCount: points.length };
    }

    // Equirectangular projection with cosine latitude correction so east-west
    // distances aren't stretched at higher latitudes.
    const midLat = points.reduce((sum, p) => sum + p.lat, 0) / points.length;
    const cosLat = Math.cos((midLat * Math.PI) / 180);
    const projected = points.map((p) => ({
      x: p.lng * cosLat,
      y: -p.lat, // SVG y grows downward
    }));

    const xs = projected.map((p) => p.x);
    const ys = projected.map((p) => p.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);

    const spanX = maxX - minX || 1e-9;
    const spanY = maxY - minY || 1e-9;
    const scale = Math.min(
      (VIEW_W - PADDING * 2) / spanX,
      (VIEW_H - PADDING * 2) / spanY
    );

    // Center the fitted route inside the viewBox
    const offsetX = (VIEW_W - spanX * scale) / 2;
    const offsetY = (VIEW_H - spanY * scale) / 2;

    const toSvg = (p: { x: number; y: number }) => ({
      x: offsetX + (p.x - minX) * scale,
      y: offsetY + (p.y - minY) * scale,
    });

    const svgPoints = projected.map(toSvg);
    const d = svgPoints
      .map(
        (p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`
      )
      .join(' ');

    return {
      path: d,
      start: svgPoints[0],
      end: svgPoints[svgPoints.length - 1],
      pointCount: points.length,
    };
  }, [polyline]);

  if (!path) return null;

  return (
    <div className={className}>
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className="w-full h-[180px] rounded-lg border border-border/60 bg-card/40"
        role="img"
        aria-label={`GPS route with ${pointCount} points`}
      >
        <path
          d={path}
          fill="none"
          stroke="var(--color-indigo-400, #818cf8)"
          strokeWidth={2.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {start && <circle cx={start.x} cy={start.y} r={4} fill="#34d399" />}
        {end && <circle cx={end.x} cy={end.y} r={4} fill="#818cf8" />}
      </svg>
    </div>
  );
}
