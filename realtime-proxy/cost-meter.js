/**
 * CostMeter — session cost from OpenAI's own usage block.
 *
 * Extracted from server.js so it can be exercised without a live upstream, an
 * API key, or a listening socket. server.js imports it; there is no second copy.
 */

// ═══════════════════════════════════════════════════════════════════════════
// COST METERING — from OpenAI's own usage block, never estimated
// ═══════════════════════════════════════════════════════════════════════════
//
// This used to be `estimateCostCents(msg)`: 0.3¢ per audio delta, 0.1¢ per
// input chunk, 0.02¢ for anything unrecognised — invented numbers with no
// relationship to what the session actually cost, published through /stats as
// `totalCostCents` and used to enforce SESSION_COST_CAP. A cap enforced on a
// fabricated number caps nothing.
//
// The OpenAI Realtime API reports real token counts on `response.done`:
//
//   response.usage = {
//     input_tokens, output_tokens, total_tokens,
//     input_token_details:  { text_tokens, audio_tokens, cached_tokens },
//     output_token_details: { text_tokens, audio_tokens },
//   }
//
// CostMeter accumulates those, priced by the REALTIME_PRICE_* environment for
// the configured model. Until the first `response.done` arrives a session's
// metered cost is 0 because nothing has been billed yet — that is a fact, not
// a placeholder, and `metered` on each stats row says so explicitly.

class CostMeter {
  constructor(prices) {
    this.prices = prices;
    this.cents = 0;
    this.responses = 0;
    this.tokens = { textIn: 0, textOut: 0, audioIn: 0, audioOut: 0 };
  }

  /** True when at least one billed response has been metered. */
  get metered() {
    return this.responses > 0;
  }

  /**
   * Record an upstream message. Returns true when it carried real usage.
   * Anything without a usage block contributes nothing — no invented charge.
   */
  record(parsed) {
    const usage = parsed?.response?.usage ?? parsed?.usage;
    if (!usage || parsed?.type !== 'response.done') return false;

    const inDetails = usage.input_token_details || {};
    const outDetails = usage.output_token_details || {};

    // Fall back to the aggregate ONLY for its own field: when the API omits the
    // per-modality split, all input tokens are priced as text. That is a
    // documented interpretation of a real number, not a substituted value.
    const textIn = num(inDetails.text_tokens, num(usage.input_tokens, 0));
    const audioIn = num(inDetails.audio_tokens, 0);
    const textOut = num(outDetails.text_tokens, num(usage.output_tokens, 0));
    const audioOut = num(outDetails.audio_tokens, 0);

    this.tokens.textIn += textIn;
    this.tokens.audioIn += audioIn;
    this.tokens.textOut += textOut;
    this.tokens.audioOut += audioOut;
    this.responses++;

    const usd =
      (textIn * this.prices.textIn +
        audioIn * this.prices.audioIn +
        textOut * this.prices.textOut +
        audioOut * this.prices.audioOut) /
      1_000_000;
    this.cents += usd * 100;
    return true;
  }
}

function num(value, fallback) {
  return Number.isFinite(value) ? value : fallback;
}

export { CostMeter, num };
