import { RefusedError } from '#core/errors'

export class MissingRateError extends RefusedError {
  constructor(currencies: string[]) {
    super('missing_rate', `no rate for ${currencies.join(', ')}; set one with quaestor rate set`, {
      currencies,
    })
  }
}
