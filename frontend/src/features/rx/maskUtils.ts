export function hexToRgb(hex: string): [number, number, number] {
  let h = (hex || "#ff0000").replace("#", "");
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  const n = parseInt(h.slice(0, 6), 16);
  if (Number.isNaN(n)) return [255, 0, 0];
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function pointInPolygon(x: number, y: number, poly: number[][]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export function centroid(poly: number[][], bbox?: number[] | null): [number, number] | null {
  if (poly.length) {
    let sx = 0, sy = 0;
    for (const p of poly) { sx += p[0]; sy += p[1]; }
    return [sx / poly.length, sy / poly.length];
  }
  if (bbox && bbox.length === 4) return [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2];
  return null;
}

/** Decode a base64 PNG mask and return a canvas tinted with `color` (alpha = mask). */
export function tintMask(b64: string, color: string, w: number, h: number): Promise<HTMLCanvasElement | null> {
  return new Promise((resolve) => {
    if (typeof document === "undefined") return resolve(null);
    const img = new Image();
    img.onload = () => {
      try {
        const c = document.createElement("canvas");
        c.width = w; c.height = h;
        const ctx = c.getContext("2d");
        if (!ctx) return resolve(null);
        ctx.drawImage(img, 0, 0, w, h);
        const data = ctx.getImageData(0, 0, w, h);
        const [r, g, b] = hexToRgb(color);
        const d = data.data;
        // mask may be encoded in alpha (if any pixel is transparent) or in luminance
        let useAlpha = false;
        for (let i = 3; i < d.length; i += 4) if (d[i] < 255) { useAlpha = true; break; }
        for (let i = 0; i < d.length; i += 4) {
          const on = (useAlpha ? d[i + 3] : d[i]) > 127;
          d[i] = r; d[i + 1] = g; d[i + 2] = b; d[i + 3] = on ? 255 : 0;
        }
        ctx.putImageData(data, 0, 0);
        resolve(c);
      } catch { resolve(null); }
    };
    img.onerror = () => resolve(null);
    img.src = `data:image/png;base64,${b64}`;
  });
}
