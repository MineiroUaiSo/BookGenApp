import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ConductionPhase } from "../../types/api";
import { advanceTime, conductionTotal, phasesAt } from "./ecgMath";

/** Player da animação de condução. `range` restringe o tempo a [lo, hi] (modo "isolar"). */
export function useConductionPlayer(phases: ConductionPhase[], range?: [number, number] | null) {
  const total = useMemo(() => conductionTotal(phases), [phases]);
  const lo = range ? range[0] : 0;
  const hi = range ? range[1] : total;
  const [t, setT] = useState(lo);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(0.25);
  const [loop, setLoop] = useState(true);
  const tRef = useRef(t);
  tRef.current = t;

  useEffect(() => { setT(lo); }, [lo, hi]);

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = now - last;
      last = now;
      const r = advanceTime(tRef.current, dt, speed, lo, hi, loop);
      tRef.current = r.t;
      setT(r.t);
      if (r.ended) { setPlaying(false); return; }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, lo, hi, loop]);

  const seek = useCallback((v: number) => setT(Math.min(hi, Math.max(lo, v))), [lo, hi]);
  const play = useCallback(() => {
    if (tRef.current >= hi) setT(lo);
    setPlaying(true);
  }, [hi, lo]);
  const pause = useCallback(() => setPlaying(false), []);
  const toggle = useCallback(() => (playing ? pause() : play()), [playing, play, pause]);
  const reset = useCallback(() => { setPlaying(false); setT(lo); }, [lo]);
  const active = useMemo(() => phasesAt(phases, t), [phases, t]);

  return { t, total, lo, hi, playing, speed, loop, active, play, pause, toggle, reset, seek, setSpeed, setLoop };
}
