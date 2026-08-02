import { useEffect, useRef } from "react"

/** The live value while `active`, the last active one once it is not.
 *
 * For content that outlives the state it was derived from: a dialog still
 * playing its exit transition re-renders after its subject is gone, and would
 * otherwise show the hole that leaves behind.
 */
export function useRetained<T>(active: boolean, value: T): T {
  const last = useRef(value)

  useEffect(() => {
    if (active) last.current = value
  }, [active, value])

  return active ? value : last.current
}
