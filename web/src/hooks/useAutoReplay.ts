import { useCallback, useEffect, useRef, useState } from "react";

import {
  idleAutoReplayProgress,
  runAutoReplay,
  type AutoReplayCallbacks,
  type AutoReplayProgress,
} from "../lib/autoReplayController";

export function useAutoReplay(
  callbacks: AutoReplayCallbacks,
  options: { maxActions?: number } = {},
  onSnapshot?: (progress: AutoReplayProgress) => void,
) {
  const [progress, setProgress] = useState<AutoReplayProgress>(idleAutoReplayProgress());
  const abortRef = useRef({ aborted: false });
  const runningRef = useRef(false);
  const callbacksRef = useRef(callbacks);
  callbacksRef.current = callbacks;
  const optionsRef = useRef(options);
  optionsRef.current = options;
  const snapshotRef = useRef(onSnapshot);

  const start = useCallback(() => {
    if (runningRef.current) return;
    runningRef.current = true;
    abortRef.current = { aborted: false };
    runAutoReplay(callbacksRef.current, optionsRef.current, abortRef.current, (snapshot) => {
      setProgress(snapshot);
      snapshotRef.current?.(snapshot);
    }).then((final) => {
      runningRef.current = false;
      setProgress(final);
    });
  }, []);

  const stop = useCallback(() => {
    abortRef.current.aborted = true;
  }, []);

  useEffect(
    () => () => {
      // React effect cleanup cancels between steps; no timers, no background work.
      abortRef.current.aborted = true;
    },
    [],
  );

  return { progress, start, stop };
}
