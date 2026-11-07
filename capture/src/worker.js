// Entry point of the capture Worker: the `scheduled` handler only, no `fetch` handler,
// so the Worker exposes no public URL (d004 D12, Capture security).

import { runPass } from "./pass.js";

/**
 * @typedef {object} Env
 * @property {R2Bucket} BUCKET                     `bikesharing-bronze`
 * @property {string} HEARTBEAT_URL                Worker secret, never logged (d004 D12, Capture security)
 * @property {{ id: string }} CF_VERSION_METADATA  Version metadata binding
 */

export default {
  /**
   * Runs one capture pass for the cron trigger.
   * @param {ScheduledController} controller
   * @param {Env} env
   * @param {ExecutionContext} ctx
   * @returns {Promise<void>}
   */
  async scheduled(controller, env, ctx) {
    await runPass(controller.scheduledTime, {
      bucket: env.BUCKET,
      heartbeatUrl: env.HEARTBEAT_URL,
      version: env.CF_VERSION_METADATA.id,
    });
  },
};
