"use client"

import { useStore } from "@tanstack/react-form"

type ValuesStore<TValues> = {
  get: () => { values: TValues }
  subscribe: (listener: (state: { values: TValues }) => void) => { unsubscribe: () => void }
}

/**
 * What a form holds right now, re-read every time it changes.
 *
 * A form announces its values only through its store: a screen that reads them
 * any other way keeps showing the answer before the owner's last one, and sends
 * that one to the server — an account he already replaced decides the currency
 * of the movement he is writing.
 *
 * One hook for every screen that derives something from what a form holds:
 * recording a movement and planning a payment behave identically on purpose.
 */
export function useFormValues<TValues>(form: { store: ValuesStore<TValues> }): TValues {
  return useStore(form.store, (state) => state.values)
}
